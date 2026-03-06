"""AI Tinkerers Warsaw — rainbow vortex shining through letter-shaped windows.

Letters act as stained-glass cutouts into a swirling rainbow spiral.
Confetti pixels rain down in the dark areas around the text.

Usage:
  uv run scripts/ai_tinkerers_vortex.py
"""

import asyncio
import colorsys
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

S = DISPLAY_SIZE
CHUNK_SIZE = 196
FINALIZE = make_cmd(0x000F, 0x3603, b"\x01\x00\x00")


def build_text_mask() -> list[list[bool]]:
    """Render 'AI / Tinkerers / Warsaw' into a 64x64 boolean mask."""
    mask = [[False] * S for _ in range(S)]

    lines = [
        ("AI", 14, 2),          # text, center_y, scale
        ("Tinkerers", 35, 1),
        ("Warsaw", 50, 1),
    ]

    for text, cy, scale in lines:
        char_w = 5 * scale
        char_h = 7 * scale
        spacing = scale
        total_w = len(text) * char_w + (len(text) - 1) * spacing
        x = (S - total_w) // 2
        y = cy - char_h // 2

        for ch in text:
            glyph = PIXEL_FONT_5x7.get(ch)
            if glyph is None or ch == " ":
                x += char_w + spacing
                continue
            for row in range(7):
                for col in range(5):
                    if glyph[row] & (1 << (4 - col)):
                        for dy in range(scale):
                            for dx in range(scale):
                                px, py = x + col * scale + dx, y + row * scale + dy
                                if 0 <= px < S and 0 <= py < S:
                                    mask[py][px] = True
            x += char_w + spacing

    return mask


# Confetti particles: (x, y_start, speed, hue)
random.seed(99)
CONFETTI = [
    (random.randint(0, S - 1), random.randint(0, S - 1),
     random.uniform(1.0, 3.0), random.random())
    for _ in range(25)
]


def generate_frames(num_frames: int = 12) -> list[Image.Image]:
    mask = build_text_mask()
    cx, cy = S / 2, S / 2
    frames = []

    for f in range(num_frames):
        img = Image.new("RGB", (S, S), (0, 0, 0))
        t = f / num_frames

        # Draw vortex through text mask + confetti in dark areas
        for y in range(S):
            for x in range(S):
                if mask[y][x]:
                    # Rainbow vortex: spiral = angle + distance, rotating over time
                    dx = x - cx
                    dy = y - cy
                    angle = math.atan2(dy, dx) / (2 * math.pi)
                    dist = math.sqrt(dx * dx + dy * dy) / (S * 0.5)
                    hue = (angle + dist * 1.5 - t * 2) % 1.0
                    sat = 0.8 + 0.2 * math.sin(dist * 6 + t * 4 * math.pi)
                    val = 0.7 + 0.3 * math.sin(angle * 8 + t * 6 * math.pi)
                    r, g, b = colorsys.hsv_to_rgb(hue, min(sat, 1), min(val, 1))
                    img.putpixel((x, y), (int(r * 255), int(g * 255), int(b * 255)))

        # Confetti in dark areas
        for cx_c, cy_c, speed, hue in CONFETTI:
            py = int(cy_c + f * speed * 3) % S
            px = cx_c + int(math.sin(f * 0.4 + hue * 10) * 1.5)
            px = px % S
            if 0 <= px < S and 0 <= py < S and not mask[py][px]:
                r, g, b = colorsys.hsv_to_rgb(hue, 0.7, 0.4)
                img.putpixel((px, py), (int(r * 255), int(g * 255), int(b * 255)))

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
    print("Generating rainbow vortex animation...")
    frames = generate_frames(12)

    gif_data = make_animated_gif(frames, 200)
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

    print("Done! Rainbow vortex through letter windows.")


asyncio.run(main())
