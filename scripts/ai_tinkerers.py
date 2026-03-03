"""Animated 'AI Tinkerers Warsaw' display for the LED backpack.

Word-by-word reveal with twinkling starfield, pixel gear icon, and rainbow text.

Usage:
  uv run scripts/ai_tinkerers.py
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

# Pixel art gear icon (11x11)
GEAR = [
    "...X.X.X...",
    "..XXXXXXX..",
    ".XXXX.XXXX.",
    "XXX...XXXXX",
    ".XX.....XX.",
    "XXX.....XXX",
    ".XX.....XX.",
    "XXXXX...XXX",
    ".XXXX.XXXX.",
    "..XXXXXXX..",
    "...X.X.X...",
]

# Twinkling star positions (fixed so they're consistent across frames)
random.seed(42)
STARS = [(random.randint(0, S - 1), random.randint(0, S - 1)) for _ in range(40)]


def draw_stars(img: Image.Image, frame: int, brightness: float = 1.0):
    """Draw twinkling stars. Each star has its own phase."""
    for i, (sx, sy) in enumerate(STARS):
        # Each star twinkles at its own rate
        twinkle = math.sin(frame * 0.8 + i * 1.7) * 0.5 + 0.5
        v = int(60 * twinkle * brightness + 20 * brightness)
        if v > 10:
            img.putpixel((sx, sy), (v, v, int(v * 1.2)))


def draw_gear(img: Image.Image, cx: int, cy: int, color: tuple[int, int, int]):
    """Draw the pixel art gear centered at (cx, cy)."""
    gw, gh = len(GEAR[0]), len(GEAR)
    ox, oy = cx - gw // 2, cy - gh // 2
    for row in range(gh):
        for col in range(gw):
            if GEAR[row][col] == "X":
                px, py = ox + col, oy + row
                if 0 <= px < S and 0 <= py < S:
                    img.putpixel((px, py), color)


def draw_text_line(img: Image.Image, text: str, cx: int, cy: int,
                   color_start: int = 0, scale: int = 1):
    """Draw a line of pixel font text centered at (cx, cy).

    scale=2 draws each pixel as a 2x2 block for big text.
    Returns the number of visible characters (for color indexing).
    """
    char_w, char_h = 5 * scale, 7 * scale
    spacing = scale
    total_w = len(text) * char_w + (len(text) - 1) * spacing
    x_start = cx - total_w // 2
    y_start = cy - char_h // 2

    ci = color_start
    for ch in text:
        glyph = PIXEL_FONT_5x7.get(ch)
        if glyph is None or ch == " ":
            x_start += char_w + spacing
            ci += 1
            continue
        color = RAINBOW[ci % len(RAINBOW)]
        for row in range(7):
            for col in range(5):
                if glyph[row] & (1 << (4 - col)):
                    for dy in range(scale):
                        for dx in range(scale):
                            px = x_start + col * scale + dx
                            py = y_start + row * scale + dy
                            if 0 <= px < S and 0 <= py < S:
                                img.putpixel((px, py), color)
        x_start += char_w + spacing
        ci += 1
    return ci


def draw_sparkle_burst(img: Image.Image, cx: int, cy: int, frame: int, radius: int):
    """Radiating sparkle burst from center."""
    n_sparks = 12
    for i in range(n_sparks):
        angle = i / n_sparks * 2 * math.pi + frame * 0.3
        r = radius * (frame % 3 + 1) / 3
        px = int(cx + r * math.cos(angle))
        py = int(cy + r * math.sin(angle))
        if 0 <= px < S and 0 <= py < S:
            # Warm white-yellow sparkle
            img.putpixel((px, py), (255, 255, 180))


def generate_frames() -> list[Image.Image]:
    """Generate animation frames for 'AI Tinkerers Warsaw'."""
    frames = []

    # Layout:
    #   "AI"        at y=16  (scale=2, big)
    #   "Tinkerers" at y=38  (scale=1)
    #   "Warsaw"    at y=52  (scale=1)
    y_ai = 16
    y_tinkerers = 38
    y_warsaw = 52
    center_x = S // 2

    # --- Frame 0-1: Starfield + gear icon ---
    for f in range(2):
        img = Image.new("RGB", (S, S), (0, 0, 0))
        draw_stars(img, f, brightness=0.6 + f * 0.2)
        gear_color = (100 + f * 60, 180 + f * 40, 255)
        draw_gear(img, center_x, S // 2, gear_color)
        if f == 1:
            draw_sparkle_burst(img, center_x, S // 2, f, 10)
        frames.append(img)

    # --- Frame 2: Gear + burst + "AI" starting to appear ---
    img = Image.new("RGB", (S, S), (0, 0, 0))
    draw_stars(img, 2, brightness=0.8)
    draw_gear(img, center_x, 6, (60, 120, 180))  # gear moves to top
    draw_sparkle_burst(img, center_x, y_ai, 2, 15)
    draw_text_line(img, "AI", center_x, y_ai, color_start=0, scale=2)
    frames.append(img)

    # --- Frame 3: "AI" big and bright, gear faded ---
    img = Image.new("RGB", (S, S), (0, 0, 0))
    draw_stars(img, 3)
    draw_gear(img, center_x, 6, (30, 60, 90))  # dim gear
    draw_text_line(img, "AI", center_x, y_ai, color_start=0, scale=2)
    frames.append(img)

    # --- Frame 4: "AI" + "Tinkerers" appears with sparkles ---
    img = Image.new("RGB", (S, S), (0, 0, 0))
    draw_stars(img, 4)
    draw_text_line(img, "AI", center_x, y_ai, color_start=0, scale=2)
    draw_sparkle_burst(img, center_x, y_tinkerers, 4, 18)
    draw_text_line(img, "Tinkerers", center_x, y_tinkerers, color_start=2)
    frames.append(img)

    # --- Frame 5: "AI" + "Tinkerers" settled ---
    img = Image.new("RGB", (S, S), (0, 0, 0))
    draw_stars(img, 5)
    draw_text_line(img, "AI", center_x, y_ai, color_start=0, scale=2)
    draw_text_line(img, "Tinkerers", center_x, y_tinkerers, color_start=2)
    frames.append(img)

    # --- Frame 6: Full text + "Warsaw" sparkle entrance ---
    img = Image.new("RGB", (S, S), (0, 0, 0))
    draw_stars(img, 6)
    draw_text_line(img, "AI", center_x, y_ai, color_start=0, scale=2)
    draw_text_line(img, "Tinkerers", center_x, y_tinkerers, color_start=2)
    draw_sparkle_burst(img, center_x, y_warsaw, 6, 14)
    draw_text_line(img, "Warsaw", center_x, y_warsaw, color_start=4)
    frames.append(img)

    # --- Frame 7-9: Full text, stars twinkle, colors shift ---
    for f in range(7, 10):
        img = Image.new("RGB", (S, S), (0, 0, 0))
        draw_stars(img, f)
        shift = f - 7  # cycle rainbow offset
        draw_text_line(img, "AI", center_x, y_ai, color_start=shift, scale=2)
        draw_text_line(img, "Tinkerers", center_x, y_tinkerers, color_start=shift + 2)
        draw_text_line(img, "Warsaw", center_x, y_warsaw, color_start=shift + 4)
        frames.append(img)

    return frames


def make_animated_gif(frames: list[Image.Image], duration_ms: int) -> bytes:
    resized = [
        f.convert("RGB").resize((S, S), Image.LANCZOS).quantize(colors=48).convert("RGB")
        for f in frames
    ]
    buf = BytesIO()
    resized[0].save(
        buf, format="GIF", save_all=True,
        append_images=resized[1:], duration=duration_ms, loop=0,
    )
    return buf.getvalue()


async def main():
    print("Generating AI Tinkerers Warsaw animation...")
    frames = generate_frames()

    # Timing: 400ms per reveal frame, 600ms lingering on full text
    durations = [400, 400, 300, 400, 300, 400, 300, 600, 600, 600]

    gif_data = make_animated_gif(frames, durations)
    num_chunks = (len(gif_data) + CHUNK_SIZE - 1) // CHUNK_SIZE
    print(f"Animated GIF: {len(frames)} frames, {len(gif_data)} bytes, {num_chunks} chunks")

    if num_chunks > 255:
        print(f"ERROR: {num_chunks} chunks exceeds protocol limit of 255.")
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

    print("Done! The backpack should show the animation.")


asyncio.run(main())
