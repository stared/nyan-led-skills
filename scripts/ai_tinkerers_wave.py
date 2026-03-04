"""Animated 'AI Tinkerers Warsaw' — bouncy rainbow wave with sparkle particles.

Each letter bobs on a sine wave while rainbow colors cycle through.
Pixel particles float upward like sparks from a soldering iron.

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

# Warm spark colors — like hot solder / welding sparks
SPARK_COLORS = [
    (255, 220, 100),
    (255, 180, 50),
    (255, 140, 30),
    (255, 100, 20),
    (200, 80, 40),
]

# Pre-generate floating particles (x, y_base, speed, phase, color_idx)
random.seed(7)
PARTICLES = [
    (
        random.randint(2, S - 3),
        random.randint(0, S - 1),
        random.uniform(1.5, 4.0),
        random.uniform(0, 2 * math.pi),
        random.randint(0, len(SPARK_COLORS) - 1),
    )
    for _ in range(30)
]


def draw_particles(img: Image.Image, frame: int, num_frames: int):
    """Draw floating spark particles that drift upward."""
    for px, y_base, speed, phase, ci in PARTICLES:
        # Float upward, wrap around
        y = (y_base - int(frame * speed)) % S
        # Horizontal wobble
        x = px + int(2 * math.sin(frame * 0.5 + phase))
        x = x % S
        # Twinkle
        bright = math.sin(frame * 0.7 + phase) * 0.5 + 0.5
        if bright > 0.3:
            color = SPARK_COLORS[ci]
            c = tuple(int(v * bright) for v in color)
            if 0 <= x < S and 0 <= y < S:
                img.putpixel((x, y), c)


def draw_glyph(img: Image.Image, ch: str, x: int, y: int,
               color: tuple[int, int, int], scale: int = 1):
    """Draw a single character at (x, y) top-left."""
    glyph = PIXEL_FONT_5x7.get(ch)
    if glyph is None or ch == " ":
        return
    for row in range(7):
        for col in range(5):
            if glyph[row] & (1 << (4 - col)):
                for dy in range(scale):
                    for dx in range(scale):
                        px = x + col * scale + dx
                        py = y + row * scale + dy
                        if 0 <= px < S and 0 <= py < S:
                            img.putpixel((px, py), color)


def text_width(text: str, scale: int = 1, spacing: int = 1) -> int:
    if not text:
        return 0
    return len(text) * 5 * scale + (len(text) - 1) * spacing


def draw_wavy_line(img: Image.Image, text: str, cx: int, cy: int,
                   frame: int, num_frames: int, color_offset: int = 0,
                   scale: int = 1, wave_amp: float = 3.0, wave_speed: float = 1.0):
    """Draw text centered at (cx, cy) with per-letter sine wave bounce and rainbow."""
    spacing = scale
    tw = text_width(text, scale, spacing)
    x = cx - tw // 2
    char_w = 5 * scale
    char_h = 7 * scale
    t = frame / num_frames * 2 * math.pi

    for i, ch in enumerate(text):
        if ch == " ":
            x += char_w + spacing
            continue
        # Sine wave vertical offset — each letter has different phase
        dy = int(wave_amp * math.sin(t * wave_speed + i * 0.8))
        color = RAINBOW[(i + color_offset) % len(RAINBOW)]
        draw_glyph(img, ch, x, cy - char_h // 2 + dy, color, scale)
        x += char_w + spacing


def generate_frames(num_frames: int = 10) -> list[Image.Image]:
    frames = []

    # Layout
    y_ai = 15
    y_tinkerers = 35
    y_warsaw = 52
    cx = S // 2

    for f in range(num_frames):
        img = Image.new("RGB", (S, S), (0, 0, 0))

        # Background particles
        draw_particles(img, f, num_frames)

        # Rainbow color offset shifts each frame for cycling effect
        color_shift = f

        # "AI" — big, bouncy, prominent
        draw_wavy_line(img, "AI", cx, y_ai, f, num_frames,
                       color_offset=color_shift, scale=2,
                       wave_amp=3, wave_speed=1.5)

        # "Tinkerers" — medium wave
        draw_wavy_line(img, "Tinkerers", cx, y_tinkerers, f, num_frames,
                       color_offset=color_shift + 2, scale=1,
                       wave_amp=2, wave_speed=1.2)

        # "Warsaw" — gentle wave
        draw_wavy_line(img, "Warsaw", cx, y_warsaw, f, num_frames,
                       color_offset=color_shift + 4, scale=1,
                       wave_amp=2, wave_speed=1.0)

        frames.append(img)

    return frames


def make_animated_gif(frames: list[Image.Image], duration_ms: int) -> bytes:
    resized = [
        f.convert("RGB").resize((S, S), Image.LANCZOS)
         .quantize(colors=48).convert("RGB")
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
    frames = generate_frames(10)

    gif_data = make_animated_gif(frames, 250)
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

    print("Done! Enjoy the bouncy rainbow text.")


asyncio.run(main())
