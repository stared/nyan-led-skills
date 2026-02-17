"""Send a gentle animated pattern to the backpack.

Usage:
  uv run scripts/send_nice.py                  # Slow rainbow wave
  uv run scripts/send_nice.py --aurora         # Aurora borealis effect
  uv run scripts/send_nice.py --breathe blue   # Gentle breathing pulse
  uv run scripts/send_nice.py --lava           # Lava lamp blobs
"""

import asyncio
import colorsys
import math
import sys
from io import BytesIO
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from bleak import BleakClient, BleakScanner
from PIL import Image, ImageDraw, ImageFilter

from display import (
    DEVICE_NAME_PREFIX,
    DISPLAY_SIZE,
    NOTIFY_UUID,
    READY,
    build_image_chunk,
    make_cmd,
    notification_handler,
    send_wait,
)

S = DISPLAY_SIZE
CHUNK_SIZE = 196
FINALIZE = make_cmd(0x000F, 0x3603, b"\x01\x00\x00")


def rainbow_wave(num_frames: int = 12) -> list[Image.Image]:
    """Slow diagonal rainbow wave shifting across the display."""
    frames = []
    for f in range(num_frames):
        img = Image.new("RGB", (S, S))
        phase = f / num_frames
        for y in range(S):
            for x in range(S):
                hue = (x / S * 0.5 + y / S * 0.3 + phase) % 1.0
                r, g, b = colorsys.hsv_to_rgb(hue, 0.6, 0.85)
                img.putpixel((x, y), (int(r * 255), int(g * 255), int(b * 255)))
        frames.append(img)
    return frames


def aurora(num_frames: int = 8) -> list[Image.Image]:
    """Aurora borealis — green/blue/purple curtains drifting."""
    frames = []
    for f in range(num_frames):
        img = Image.new("RGB", (S, S))
        t = f / num_frames * 2 * math.pi
        for y in range(S):
            for x in range(S):
                # Vertical curtain waves
                wave1 = math.sin(x / S * 4 + t) * 0.5 + 0.5
                wave2 = math.sin(x / S * 6 - t * 0.7 + 1.5) * 0.5 + 0.5
                # Fade toward top (aurora is higher up)
                vert = 1.0 - (y / S) ** 0.6
                intensity = (wave1 * 0.6 + wave2 * 0.4) * vert
                # Green-cyan-purple palette
                hue = 0.35 + wave2 * 0.25  # green to purple range
                r, g, b = colorsys.hsv_to_rgb(hue % 1.0, 0.7, intensity * 0.9)
                img.putpixel((x, y), (int(r * 255), int(g * 255), int(b * 255)))
        frames.append(img)
    return frames


def breathe(color_name: str = "blue", num_frames: int = 10) -> list[Image.Image]:
    """Gentle pulsing glow that breathes in and out."""
    color_map = {
        "red": (0.0, 0.8), "green": (0.33, 0.7), "blue": (0.6, 0.8),
        "purple": (0.75, 0.8), "cyan": (0.5, 0.7), "orange": (0.08, 0.9),
        "pink": (0.9, 0.6),
    }
    hue, sat = color_map.get(color_name, (0.6, 0.8))

    frames = []
    for f in range(num_frames):
        # Smooth sine breathing curve
        t = f / num_frames * 2 * math.pi
        brightness = 0.25 + 0.6 * (math.sin(t) * 0.5 + 0.5)

        img = Image.new("RGB", (S, S))
        cx, cy = S / 2, S / 2
        max_dist = math.sqrt(cx ** 2 + cy ** 2)

        for y in range(S):
            for x in range(S):
                dist = math.sqrt((x - cx) ** 2 + (y - cy) ** 2) / max_dist
                # Radial glow - brighter in center
                local_bright = brightness * (1.0 - dist * 0.6)
                local_sat = sat * (0.5 + dist * 0.5)
                r, g, b = colorsys.hsv_to_rgb(hue, local_sat, max(0, local_bright))
                img.putpixel((x, y), (int(r * 255), int(g * 255), int(b * 255)))
        frames.append(img)
    return frames


def lava(num_frames: int = 8) -> list[Image.Image]:
    """Lava lamp — warm blobs drifting upward."""
    frames = []
    for f in range(num_frames):
        img = Image.new("RGB", (S, S), (15, 0, 5))
        draw = ImageDraw.Draw(img)
        t = f / num_frames * 2 * math.pi

        blobs = [
            (0.3, 0.5, 0.22, 0.7, (200, 50, 10)),
            (0.7, 0.4, 0.18, 1.3, (220, 80, 5)),
            (0.5, 0.7, 0.20, 0.9, (180, 30, 15)),
            (0.4, 0.3, 0.15, 1.6, (240, 60, 0)),
        ]

        for bx, by, radius, speed, color in blobs:
            cx = int((bx + 0.08 * math.sin(t * speed + bx * 5)) * S)
            cy = int((by + 0.12 * math.sin(t * speed * 0.8 + by * 3)) * S)
            r = int(radius * S)
            draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=color)

        img = img.filter(ImageFilter.GaussianBlur(radius=6))
        frames.append(img)
    return frames


def make_animated_gif(frames: list[Image.Image], duration_ms: int, max_colors: int = 32) -> bytes:
    """Create animated GIF, quantizing to max_colors to keep file size small."""
    resized = [
        f.convert("RGB").resize((S, S), Image.LANCZOS).quantize(colors=max_colors).convert("RGB")
        for f in frames
    ]
    buf = BytesIO()
    resized[0].save(
        buf, format="GIF", save_all=True,
        append_images=resized[1:], duration=duration_ms, loop=0,
    )
    return buf.getvalue()


async def main():
    args = sys.argv[1:]
    delay_ms = 200

    if "--aurora" in args:
        print("Generating aurora borealis...")
        frames = aurora()
        delay_ms = 250
    elif "--breathe" in args:
        idx = args.index("--breathe")
        color = args[idx + 1] if idx + 1 < len(args) else "blue"
        print(f"Generating {color} breathing pulse...")
        frames = breathe(color)
        delay_ms = 150
    elif "--lava" in args:
        print("Generating lava lamp...")
        frames = lava()
        delay_ms = 200
    else:
        print("Generating rainbow wave...")
        frames = rainbow_wave()
        delay_ms = 250

    gif_data = make_animated_gif(frames, delay_ms)
    num_chunks = (len(gif_data) + CHUNK_SIZE - 1) // CHUNK_SIZE
    print(f"Animated GIF: {len(frames)} frames, {len(gif_data)} bytes, {num_chunks} chunks")

    if num_chunks > 255:
        print(f"ERROR: {num_chunks} chunks exceeds protocol limit of 255 (total_chunks is 1 byte).")
        print("Reduce frame count or image complexity.")
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
                print(f"  chunk {idx}/{num_chunks} → ERR status={status}")
            await asyncio.sleep(0.3)

        await send_wait(client, FINALIZE)
        await client.stop_notify(NOTIFY_UUID)

    print("Done! Enjoy.")


asyncio.run(main())
