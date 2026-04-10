"""AI Breakfast Warsaw — coffee cup with rising steam and rainbow text.

Usage:
  uv run scripts/ai_breakfast_warsaw.py
"""

import asyncio
import math
import random
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

# Coffee cup pixel art (16 wide x 12 tall), placed at bottom-right
# . = transparent, C = cup body, H = handle, L = coffee liquid, F = foam, S = saucer
CUP_ART = [
    "....FFFFFFFF....",  # foam top
    "...FFFFFFFFFF...",  # foam
    "...LLLLLLLLLL...",  # coffee surface
    "...CCLLLLLLCC...",  # cup + coffee
    "...CCLLLLLLCCHH.",  # cup + handle
    "...CCLLLLLLCCH.H",  # cup + handle
    "...CCLLLLLLCCH.H",  # cup + handle
    "...CCLLLLLLCCHH.",  # cup + handle
    "...CCCCCCCCCC...",  # cup bottom
    "....CCCCCCCC....",  # cup base
    ".SSSSSSSSSSSSSS.",  # saucer
    "..SSSSSSSSSSSS..",  # saucer bottom
]

CUP_COLORS = {
    "C": (220, 220, 230),  # white ceramic
    "H": (200, 200, 210),  # handle
    "L": (90, 50, 20),     # dark coffee
    "F": (210, 180, 140),  # creamy foam
    "S": (190, 190, 200),  # saucer
}

CUP_W = len(CUP_ART[0])
CUP_H = len(CUP_ART)
CUP_OX = S - CUP_W - 2   # bottom-right corner
CUP_OY = S - CUP_H - 1


def draw_warm_bg(img, frame):
    """Dark warm gradient — coffee shop ambiance."""
    t = frame / 8 * 2 * math.pi
    for y in range(S):
        ny = y / S
        r = int(25 + 18 * ny + 5 * math.sin(t + ny * 3))
        g = int(12 + 8 * ny + 3 * math.sin(t * 0.8))
        b = int(8 + 5 * ny)
        for x in range(S):
            img.putpixel((x, y), (r, g, b))


def draw_coffee_cup(img):
    """Draw the pixel-art coffee cup."""
    for row_idx, row in enumerate(CUP_ART):
        for col_idx, ch in enumerate(row):
            if ch == ".":
                continue
            color = CUP_COLORS.get(ch)
            if color:
                px = CUP_OX + col_idx
                py = CUP_OY + row_idx
                if 0 <= px < S and 0 <= py < S:
                    img.putpixel((px, py), color)


def draw_steam(img, frame):
    """Animated steam wisps rising from the coffee cup."""
    random.seed(77)
    cup_cx = CUP_OX + CUP_W // 2
    t = frame / 8 * 2 * math.pi

    for wisp in range(3):
        base_x = cup_cx - 3 + wisp * 3
        speed = 0.7 + wisp * 0.3
        for dy in range(12):
            progress = dy / 12
            # Wisp rises and fades
            fade = 1.0 - progress
            # Sinusoidal drift
            drift = math.sin(t * speed + dy * 0.5 + wisp * 2) * (2 + dy * 0.3)
            px = int(base_x + drift)
            py = CUP_OY - 2 - dy - int(frame * 0.8 + wisp) % 3
            if 0 <= px < S and 0 <= py < S and fade > 0.2:
                v = int(180 * fade)
                img.putpixel((px, py), (v, v, min(255, int(v * 1.1))))


def draw_text_rainbow(img, text, cx, y, color_offset=0):
    """Draw pixel font text centered at cx with cycling rainbow colors."""
    char_w, spacing = 5, 1
    total_w = len(text) * char_w + (len(text) - 1) * spacing
    x = cx - total_w // 2
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
                    px, py = x + col, y + row
                    if 0 <= px < S and 0 <= py < S:
                        img.putpixel((px, py), color)
        x += char_w + spacing
        ci += 1


def generate_frames():
    frames = []
    # Text on the left side, cup on the right
    text_cx = 22

    for f in range(8):
        img = Image.new("RGB", (S, S), (0, 0, 0))

        draw_warm_bg(img, f)
        draw_coffee_cup(img)
        draw_steam(img, f)

        # Text stacked on the left
        draw_text_rainbow(img, "AI", text_cx, 10, color_offset=f)
        draw_text_rainbow(img, "Breakfast", text_cx, 22, color_offset=f + 2)
        draw_text_rainbow(img, "Warsaw", text_cx, 34, color_offset=f + 5)

        frames.append(img)

    return frames


def make_animated_gif(frames, duration_ms):
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
    print("Generating AI Breakfast Warsaw...")
    frames = generate_frames()

    gif_data = make_animated_gif(frames, 300)
    num_chunks = (len(gif_data) + CHUNK_SIZE - 1) // CHUNK_SIZE
    print(f"Animated GIF: {len(frames)} frames, {len(gif_data)} bytes, {num_chunks} chunks")

    if num_chunks > 255:
        print(f"ERROR: {num_chunks} chunks exceeds protocol limit.")
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

    print("Done! AI Breakfast Warsaw is on display.")


asyncio.run(main())
