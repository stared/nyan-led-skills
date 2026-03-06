"""AI Breakfast — pixel art coffee mug with curling steam and rainbow text.

Usage:
  uv run scripts/ai_breakfast.py
"""

import asyncio
import math
import sys
from io import BytesIO
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from bleak import BleakClient, BleakScanner
from PIL import Image

from display import (
    DEVICE_NAME_PREFIX,
    DISPLAY_SIZE,
    NOTIFY_UUID,
    PIXEL_FONT_5x7,
    RAINBOW,
    READY,
    build_image_chunk,
    make_cmd,
    notification_handler,
    send_wait,
)

S = DISPLAY_SIZE
CHUNK_SIZE = 196
FINALIZE = make_cmd(0x000F, 0x3603, b"\x01\x00\x00")

# Coffee mug pixel art (18 wide x 13 tall)
# W=mug(white), c=coffee(brown), h=handle(white), s=saucer(gray), .=empty
MUG_ART = [
    "..WWWWWWWWWWWW......",  # rim
    "..WccccccccccW......",
    "..WccccccccccW..WW..",
    "..WccccccccccW.W..W.",
    "..WccccccccccW.W..W.",
    "..WccccccccccW.W..W.",
    "..WccccccccccW..WW..",
    "..WccccccccccW......",
    "..WccccccccccW......",
    "..WWWWWWWWWWWW......",
    "...ssssssssss.......",  # saucer
    "..ssssssssssss......",
]

MUG_COLORS = {
    "W": (220, 220, 230),   # white ceramic
    "c": (100, 55, 20),     # dark coffee
    "s": (160, 160, 170),   # saucer gray
}

# Steam wisp paths — each is a list of (dx, dy) offsets from the mug top
# Two curling wisps that shift upward over time
WISP_SHAPES = [
    # Left wisp (sine curve going left)
    [(0, 0), (0, -1), (-1, -2), (-1, -3), (0, -4), (0, -5), (-1, -6), (-1, -7), (0, -8)],
    # Right wisp (sine curve going right)
    [(0, 0), (0, -1), (1, -2), (1, -3), (0, -4), (0, -5), (1, -6), (1, -7), (0, -8)],
    # Center wisp
    [(0, 0), (0, -1), (0, -2), (-1, -3), (0, -4), (1, -5), (0, -6), (0, -7), (-1, -8)],
]

STEAM_COLORS = [
    (180, 180, 200),
    (150, 150, 170),
    (120, 120, 145),
    (90, 90, 115),
    (60, 60, 85),
]


def draw_mug(img: Image.Image, ox: int, oy: int):
    """Draw the coffee mug at offset (ox, oy)."""
    for row_idx, row in enumerate(MUG_ART):
        for col_idx, ch in enumerate(row):
            color = MUG_COLORS.get(ch)
            if color:
                px, py = ox + col_idx, oy + row_idx
                if 0 <= px < S and 0 <= py < S:
                    img.putpixel((px, py), color)


def draw_steam(img: Image.Image, mug_ox: int, mug_oy: int, frame: int, num_frames: int):
    """Draw animated steam wisps rising from the mug."""
    # Steam origins (above the mug rim)
    origins = [
        (mug_ox + 5, mug_oy - 1),
        (mug_ox + 9, mug_oy - 1),
        (mug_ox + 13, mug_oy - 1),
    ]

    rise = frame * 1.5  # pixels to rise per frame

    for wisp_idx, (base_x, base_y) in enumerate(origins):
        wisp = WISP_SHAPES[wisp_idx % len(WISP_SHAPES)]
        for i, (dx, dy) in enumerate(wisp):
            # Each point rises upward over time, wrapping
            y_off = dy - rise
            # Horizontal wobble that changes with time
            wobble = int(1.5 * math.sin(frame * 0.6 + i * 0.8 + wisp_idx * 2))
            px = base_x + dx + wobble
            py = int(base_y + y_off)

            if 0 <= px < S and 0 <= py < S:
                # Fade with height (further up = dimmer)
                fade_idx = min(i, len(STEAM_COLORS) - 1)
                # Also fade based on how far it's risen
                img.putpixel((px, py), STEAM_COLORS[fade_idx])


def draw_text_line(img: Image.Image, text: str, cx: int, cy: int,
                   color_offset: int = 0, scale: int = 1):
    """Draw centered text with rainbow colors."""
    char_w = 5 * scale
    char_h = 7 * scale
    spacing = scale
    total_w = len(text) * char_w + (len(text) - 1) * spacing
    x = cx - total_w // 2
    y = cy - char_h // 2

    ci = color_offset
    for ch in text:
        glyph = PIXEL_FONT_5x7.get(ch)
        if glyph is None or ch == " ":
            x += char_w + spacing
            ci += 1
            continue
        color = RAINBOW[ci % len(RAINBOW)]
        for row in range(7):
            for col in range(5):
                if glyph[row] & (1 << (4 - col)):
                    for dy in range(scale):
                        for dx in range(scale):
                            px, py = x + col * scale + dx, y + row * scale + dy
                            if 0 <= px < S and 0 <= py < S:
                                img.putpixel((px, py), color)
        x += char_w + spacing
        ci += 1


def generate_frames(num_frames: int = 10) -> list[Image.Image]:
    frames = []

    # Layout
    cx = S // 2
    mug_ox = 22   # mug left edge x
    mug_oy = 38   # mug top edge y

    for f in range(num_frames):
        img = Image.new("RGB", (S, S), (0, 0, 0))

        # Steam behind the mug (drawn first)
        draw_steam(img, mug_ox, mug_oy, f, num_frames)

        # Coffee mug
        draw_mug(img, mug_ox, mug_oy)

        # Text with cycling rainbow
        draw_text_line(img, "AI", cx, 10, color_offset=f, scale=2)
        draw_text_line(img, "Breakfast", cx, 28, color_offset=f + 2)

        frames.append(img)

    return frames


def make_animated_gif(frames: list[Image.Image], duration_ms: int) -> bytes:
    quantized = [
        f.convert("RGB").quantize(colors=48).convert("RGB")
        for f in frames
    ]
    buf = BytesIO()
    quantized[0].save(
        buf, format="GIF", save_all=True,
        append_images=quantized[1:], duration=duration_ms, loop=0,
    )
    return buf.getvalue()


async def main():
    print("Generating AI Breakfast animation...")
    frames = generate_frames(10)

    gif_data = make_animated_gif(frames, 250)
    num_chunks = (len(gif_data) + CHUNK_SIZE - 1) // CHUNK_SIZE
    print(f"Animated GIF: {len(frames)} frames, {len(gif_data)} bytes, {num_chunks} chunks")

    if num_chunks > 255:
        print(f"ERROR: too many chunks ({num_chunks}).")
        return

    print("\nScanning for backpack...")
    device = await BleakScanner.find_device_by_filter(
        lambda d, adv: (adv.local_name or "").startswith(DEVICE_NAME_PREFIX),
        timeout=10,
    )
    if not device:
        print("Backpack not found!")
        return

    print(f"Found: {device.name}")

    async with BleakClient(device) as client:
        await client.start_notify(NOTIFY_UUID, notification_handler)
        print(f"Connected (MTU: {client.mtu_size})")

        await send_wait(client, READY)
        for idx in range(num_chunks):
            chunk = gif_data[idx * CHUNK_SIZE : (idx + 1) * CHUNK_SIZE]
            pkt = build_image_chunk(idx, chunk, num_chunks)
            status = await send_wait(client, pkt)
            if status != 0:
                print(f"  chunk {idx}/{num_chunks} -> ERR status={status}")
            await asyncio.sleep(0.3)

        await send_wait(client, FINALIZE)
        await client.stop_notify(NOTIFY_UUID)

    print("Done! Enjoy your AI Breakfast.")


asyncio.run(main())
