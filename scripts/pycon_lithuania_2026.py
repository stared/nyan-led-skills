"""PyCon Lithuania 2026 — Lithuanian aurora with slithering Python snake.

Flowing northern lights in Lithuanian flag colors (yellow/green/red)
over a dark sky, with "PyCon" and "LT 2026" text and an animated
Python snake at the bottom.

Usage:
  uv run scripts/pycon_lithuania_2026.py            # send to backpack
  uv run scripts/pycon_lithuania_2026.py --preview   # save preview GIF
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
    READY,
    build_image_chunk,
    make_cmd,
    notification_handler,
    send_wait,
)

S = DISPLAY_SIZE  # 64
CHUNK_SIZE = 196
FINALIZE = make_cmd(0x000F, 0x3603, b"\x01\x00\x00")
NUM_FRAMES = 10

# Lithuanian flag colors
LT_YELLOW = (253, 185, 19)
LT_GREEN = (0, 106, 68)
LT_RED = (193, 39, 45)


def lerp_color(c1, c2, t):
    return tuple(int(a + (b - a) * t) for a, b in zip(c1, c2))


def draw_sky(img, frame):
    """Dark sky with subtle gradient."""
    t = frame / NUM_FRAMES * 2 * math.pi
    for y in range(S):
        ny = y / S
        r = max(0, min(255, int(6 + 5 * ny + 3 * math.sin(t + ny * 2))))
        g = max(0, min(255, int(4 + 3 * ny + 2 * math.sin(t * 0.7))))
        b = max(0, min(255, int(16 + 10 * ny + 4 * math.sin(t * 1.2 + ny))))
        for x in range(S):
            img.putpixel((x, y), (r, g, b))


def draw_stars(img, frame):
    """Twinkling stars."""
    random.seed(2026)
    for _ in range(25):
        sx = random.randint(0, S - 1)
        sy = random.randint(0, 22)
        phase = random.random() * 10
        brightness = random.uniform(0.3, 1.0)
        twinkle = math.sin(frame * 0.7 + phase) * 0.4 + 0.6
        v = int(100 * brightness * twinkle)
        if v > 15:
            img.putpixel((sx, sy), (v, v, min(255, int(v * 1.1))))


def draw_lt_aurora(img, frame):
    """Northern lights in Lithuanian flag colors: yellow, green, red."""
    t = frame / NUM_FRAMES * 2 * math.pi
    for x in range(S):
        nx = x / S
        wave1 = math.sin(nx * 5 + t) * 0.5 + 0.5
        wave2 = math.sin(nx * 7 - t * 0.6 + 1.5) * 0.5 + 0.5
        wave3 = math.sin(nx * 3 + t * 0.4 + 3.0) * 0.5 + 0.5

        curtain = wave1 * 0.5 + wave2 * 0.3 + wave3 * 0.2

        for y in range(3, 28):
            ny = (y - 3) / 25
            vert = math.exp(-((ny - 0.4) ** 2) / 0.08)
            intensity = curtain * vert * 0.9

            if intensity < 0.05:
                continue

            color_t = (wave2 + wave3 * 0.3) % 1.0
            if color_t < 0.33:
                base = lerp_color(LT_YELLOW, LT_GREEN, color_t / 0.33)
            elif color_t < 0.66:
                base = lerp_color(LT_GREEN, LT_RED, (color_t - 0.33) / 0.33)
            else:
                base = lerp_color(LT_RED, LT_YELLOW, (color_t - 0.66) / 0.34)

            r = int(base[0] * intensity)
            g = int(base[1] * intensity)
            b = int(base[2] * intensity)

            old = img.getpixel((x, y))
            img.putpixel(
                (x, y),
                (min(255, old[0] + r), min(255, old[1] + g), min(255, old[2] + b)),
            )


def draw_text_lt_gradient(img, text, cx, y, frame=0):
    """Draw text with Lithuanian flag gradient (yellow -> green -> red) and shimmer."""
    char_w, spacing = 5, 1
    total_w = len(text) * char_w + (len(text) - 1) * spacing
    x = cx - total_w // 2
    n = len(text.replace(" ", ""))
    ci = 0
    for ch in text:
        glyph = PIXEL_FONT_5x7.get(ch)
        if glyph is None or ch == " ":
            x += char_w + spacing
            continue
        t = ci / max(1, n - 1)
        shimmer = math.sin(frame * 0.8 + ci * 0.7) * 0.12
        t = max(0, min(1, t + shimmer))
        if t < 0.5:
            color = lerp_color(LT_YELLOW, LT_GREEN, t / 0.5)
        else:
            color = lerp_color(LT_GREEN, LT_RED, (t - 0.5) / 0.5)
        color = tuple(min(255, int(v * 1.4)) for v in color)
        for row in range(7):
            for col in range(5):
                if glyph[row] & (1 << (4 - col)):
                    px, py = x + col, y + row
                    if 0 <= px < S and 0 <= py < S:
                        img.putpixel((px, py), color)
        x += char_w + spacing
        ci += 1


def draw_text_white(img, text, cx, y, frame=0):
    """Draw text in bright white with subtle pulse."""
    char_w, spacing = 5, 1
    total_w = len(text) * char_w + (len(text) - 1) * spacing
    x = cx - total_w // 2
    pulse = 0.85 + 0.15 * math.sin(frame * 0.5)
    v = int(255 * pulse)
    for ch in text:
        glyph = PIXEL_FONT_5x7.get(ch)
        if glyph is None or ch == " ":
            x += char_w + spacing
            continue
        for row in range(7):
            for col in range(5):
                if glyph[row] & (1 << (4 - col)):
                    px, py = x + col, y + row
                    if 0 <= px < S and 0 <= py < S:
                        img.putpixel((px, py), (v, v, v))
        x += char_w + spacing


def draw_snake(img, frame):
    """Animated Python snake in Lithuanian flag colors slithering at the bottom."""
    t = frame / NUM_FRAMES * 2 * math.pi
    y_base = 53

    # Body: 38 segments following a sine wave
    for seg in range(38):
        x = 8 + seg
        y = y_base + int(math.sin(t + seg * 0.22) * 2.5)

        stripe = (seg // 4) % 3
        color = [LT_YELLOW, LT_GREEN, LT_RED][stripe]

        # Taper the tail (first 6 segments)
        thickness = 3 if seg > 5 else max(1, (seg + 1) * 3 // 6)

        for dy in range(thickness):
            px, py = x, y + dy
            if 0 <= px < S and 0 <= py < S:
                img.putpixel((px, py), color)

    # Head (wider, rounded)
    hx = 46
    hy = y_base + int(math.sin(t + 38 * 0.22) * 2.5)
    for dx, dy in [
        (0, 0), (1, 0), (2, 0), (3, 0),
        (0, 1), (1, 1), (2, 1), (3, 1), (4, 1),
        (0, 2), (1, 2), (2, 2), (3, 2), (4, 2),
        (1, 3), (2, 3), (3, 3),
    ]:
        px, py = hx + dx, hy + dy
        if 0 <= px < S and 0 <= py < S:
            img.putpixel((px, py), LT_GREEN)

    # Eyes
    for ey in [hy, hy + 2]:
        ex = hx + 3
        if 0 <= ex < S and 0 <= ey < S:
            img.putpixel((ex, ey), (255, 255, 255))

    # Tongue (flickers every other frame)
    if frame % 3 != 0:
        ty = hy + 1
        for i in range(2):
            tx = hx + 5 + i
            if 0 <= tx < S and 0 <= ty < S:
                img.putpixel((tx, ty), (220, 40, 40))
        # Fork
        for fy in [ty - 1, ty + 1]:
            fx = hx + 7
            if 0 <= fx < S and 0 <= fy < S:
                img.putpixel((fx, fy), (220, 40, 40))


def draw_sparkles(img, frame):
    """Floating sparkles in Lithuanian colors."""
    random.seed(42)
    colors = [LT_YELLOW, LT_GREEN, LT_RED]
    for _ in range(12):
        base_x = random.randint(0, S - 1)
        base_y = random.randint(44, S - 4)
        speed = random.uniform(0.4, 0.9)
        phase = random.random() * 10
        color = colors[random.randint(0, 2)]

        y = base_y - int(frame * speed * 1.5) % 18
        x = base_x + int(math.sin(frame * 0.5 + phase) * 2)

        brightness = math.sin(frame * 0.8 + phase) * 0.4 + 0.6
        if brightness > 0.3 and 0 <= x < S and 0 <= y < S:
            c = tuple(int(v * brightness) for v in color)
            img.putpixel((x, y), c)


def generate_frames():
    frames = []
    cx = S // 2

    for f in range(NUM_FRAMES):
        img = Image.new("RGB", (S, S), (0, 0, 0))

        draw_sky(img, f)
        draw_stars(img, f)
        draw_lt_aurora(img, f)
        draw_sparkles(img, f)
        draw_snake(img, f)

        draw_text_white(img, "PyCon", cx, 30, f)
        draw_text_lt_gradient(img, "LT 2026", cx, 40, f)

        frames.append(img)

    return frames


def make_animated_gif(frames, duration_ms):
    quantized = [
        f.convert("RGB").quantize(colors=48).convert("RGB") for f in frames
    ]
    buf = BytesIO()
    quantized[0].save(
        buf,
        format="GIF",
        save_all=True,
        append_images=quantized[1:],
        duration=duration_ms,
        loop=0,
    )
    return buf.getvalue()


async def main():
    preview = "--preview" in sys.argv

    print("Generating PyCon Lithuania 2026...")
    frames = generate_frames()

    gif_data = make_animated_gif(frames, 350)
    num_chunks = (len(gif_data) + CHUNK_SIZE - 1) // CHUNK_SIZE
    print(f"Animated GIF: {len(frames)} frames, {len(gif_data)} bytes, {num_chunks} chunks")

    if num_chunks > 255:
        print(f"ERROR: {num_chunks} chunks exceeds protocol limit.")
        return

    if preview:
        out = Path(__file__).parent / "pycon_lithuania_2026_preview.gif"
        out.write_bytes(gif_data)
        print(f"Preview saved: {out}")
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

    print("Done! PyCon Lithuania 2026 is on display.")


asyncio.run(main())
