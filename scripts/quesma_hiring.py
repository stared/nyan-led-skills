"""Quesma hiring — arcade-style 'Can you outsmart AI?' animation.

Usage:
  uv run scripts/quesma_hiring.py          # preview only (no send)
  uv run scripts/quesma_hiring.py --send   # send to backpack
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
    READY,
    build_image_chunk,
    make_cmd,
    notification_handler,
    send_wait,
)

S = DISPLAY_SIZE
CHUNK_SIZE = 196
FINALIZE = make_cmd(0x000F, 0x3603, b"\x01\x00\x00")

# Neon arcade palette
BLACK = (0, 0, 0)
NEON_PINK = (255, 50, 180)
NEON_CYAN = (0, 255, 240)
NEON_GREEN = (50, 255, 80)
NEON_YELLOW = (255, 255, 50)
NEON_ORANGE = (255, 140, 30)
WHITE = (255, 255, 255)
DIM_PURPLE = (40, 20, 60)

# Pixel art: robot head (11x9)
ROBOT = [
    "...CCCCC...",
    "..CCCCCCC..",
    "..C.CCC.C..",
    "..CCCCCCC..",
    "...C.C.C...",
    "..CCCCCCC..",
    "..CC.C.CC..",
    "..CCCCCCC..",
    "...CC.CC...",
]
ROBOT_PAL = {"C": NEON_CYAN}

# Pixel art: human brain (11x8)
BRAIN = [
    "...PPPPP...",
    "..PPPPPPP..",
    ".PPPPPPPP..",
    ".PPPPPPPPP.",
    ".PPPPPPPPP.",
    "..PPPPPPP..",
    "...PPPPP...",
    "....PPP....",
]
BRAIN_PAL = {"P": NEON_PINK}

# Pixel art: "VS" lightning bolt (7x9)
BOLT = [
    "..YYYY.",
    ".YYYY..",
    "YYYY...",
    "YYYYYY.",
    ".YYYYYY",
    "...YYYY",
    "..YYYY.",
    ".YYYY..",
    "YYYY...",
]
BOLT_PAL = {"Y": NEON_YELLOW}

# Pixel art: question mark block (9x9)
QBLOCK = [
    "OOOOOOOOO",
    "OGGGGGGO.",
    "OG.GGG.GO",
    "OGGGGGOGO",
    "OGGG.GOGO",
    "OGG.GGOGO",
    "OGGGGGGO.",
    "OGG.GGGO.",
    "OOOOOOOOO",
]
QBLOCK_PAL = {"O": NEON_ORANGE, "G": NEON_YELLOW}


def draw_art(img, art, palette, cx, cy):
    h = len(art)
    w = max(len(r) for r in art)
    ox, oy = cx - w // 2, cy - h // 2
    for ri, row in enumerate(art):
        for ci, ch in enumerate(row):
            c = palette.get(ch)
            if c:
                px, py = ox + ci, oy + ri
                if 0 <= px < S and 0 <= py < S:
                    img.putpixel((px, py), c)


def draw_text(img, text, cx, cy, color, scale=1):
    char_w, char_h, spacing = 5 * scale, 7 * scale, scale
    total_w = len(text) * char_w + (len(text) - 1) * spacing
    x = cx - total_w // 2
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
                                img.putpixel((px, py), color)
        x += char_w + spacing


def draw_grid_bg(img, brightness=20):
    """Subtle grid background for arcade feel."""
    for x in range(0, S, 8):
        for y in range(S):
            img.putpixel((x, y), (brightness, brightness // 2, brightness))
    for y in range(0, S, 8):
        for x in range(S):
            img.putpixel((x, y), (brightness, brightness // 2, brightness))


def generate_frames() -> list[Image.Image]:
    frames = []
    cx = S // 2

    # --- Frame 0: QUESMA title ---
    img = Image.new("RGB", (S, S), DIM_PURPLE)
    draw_grid_bg(img, 25)
    draw_text(img, "QUESMA", cx, 20, NEON_CYAN)
    # Underline
    for x in range(12, S - 12):
        img.putpixel((x, 25), NEON_PINK)
    draw_text(img, "evals", cx, 34, NEON_GREEN)
    draw_text(img, "for AI", cx, 46, NEON_GREEN)
    draw_text(img, "agents", cx, 56, NEON_GREEN)
    frames.append(img)

    # --- Frame 1: Brain VS Robot ---
    img = Image.new("RGB", (S, S), DIM_PURPLE)
    draw_grid_bg(img, 20)
    draw_art(img, BRAIN, BRAIN_PAL, 16, 18)
    draw_art(img, BOLT, BOLT_PAL, cx, 18)
    draw_art(img, ROBOT, ROBOT_PAL, 48, 18)
    draw_text(img, "Can you", cx, 36, WHITE)
    draw_text(img, "outsmart", cx, 47, NEON_YELLOW)
    draw_text(img, "AI?", cx, 57, NEON_CYAN)
    frames.append(img)

    # --- Frame 2: Question block + challenge ---
    img = Image.new("RGB", (S, S), DIM_PURPLE)
    draw_grid_bg(img, 20)
    draw_art(img, QBLOCK, QBLOCK_PAL, cx, 16)
    draw_text(img, "Create", cx, 30, NEON_GREEN)
    draw_text(img, "tasks AI", cx, 41, WHITE)
    draw_text(img, "can't do", cx, 52, NEON_PINK)
    frames.append(img)

    # --- Frame 3: What we do ---
    img = Image.new("RGB", (S, S), DIM_PURPLE)
    draw_grid_bg(img, 20)
    draw_text(img, "We test", cx, 10, NEON_ORANGE)
    draw_text(img, "AI with", cx, 21, WHITE)
    draw_text(img, "hard", cx, 34, NEON_CYAN)
    draw_text(img, "real-life", cx, 45, NEON_CYAN)
    draw_text(img, "tasks", cx, 56, NEON_YELLOW)
    frames.append(img)

    # --- Frame 4: Hiring! ---
    img = Image.new("RGB", (S, S), DIM_PURPLE)
    draw_grid_bg(img, 25)
    draw_text(img, "We're", cx, 12, NEON_YELLOW)
    draw_text(img, "hiring!", cx, 24, NEON_PINK)
    # Decorative line
    for x in range(8, S - 8):
        img.putpixel((x, 33), NEON_CYAN)
    draw_text(img, "quesma", cx, 40, NEON_CYAN)
    draw_text(img, ".com", cx, 52, NEON_GREEN)
    frames.append(img)

    # --- Frame 5: Join us ---
    img = Image.new("RGB", (S, S), (20, 5, 35))
    draw_grid_bg(img, 30)
    draw_text(img, "JOIN", cx, 10, NEON_YELLOW)
    draw_text(img, "the", cx, 21, WHITE)
    draw_text(img, "puzzle", cx, 34, NEON_PINK)
    draw_text(img, "makers!", cx, 46, NEON_GREEN)
    # Sparkle dots
    sparkles = [(8, 8), (55, 12), (12, 55), (52, 50), (30, 6), (40, 58)]
    for sx, sy in sparkles:
        img.putpixel((sx, sy), NEON_YELLOW)
    frames.append(img)

    return frames


def make_animated_gif(frames, durations):
    quantized = [
        f.convert("RGB").quantize(colors=32).convert("RGB")
        for f in frames
    ]
    buf = BytesIO()
    quantized[0].save(
        buf, format="GIF", save_all=True,
        append_images=quantized[1:], duration=durations, loop=0,
    )
    return buf.getvalue()


def save_preview(frames, durations):
    """Save a preview GIF to disk."""
    gif_data = make_animated_gif(frames, durations)
    out = Path(__file__).parent / "quesma_hiring_preview.gif"
    out.write_bytes(gif_data)
    print(f"Preview saved: {out} ({len(gif_data)} bytes)")
    return gif_data


async def send_to_backpack(gif_data):
    num_chunks = (len(gif_data) + CHUNK_SIZE - 1) // CHUNK_SIZE
    print(f"Animated GIF: {len(gif_data)} bytes, {num_chunks} chunks")

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

    print("Done! Quesma is hiring.")


async def main():
    print("Generating Quesma hiring animation...")
    frames = generate_frames()
    durations = [4000, 4000, 4000, 4000, 3500, 3500]

    gif_data = save_preview(frames, durations)

    if "--send" in sys.argv:
        await send_to_backpack(gif_data)
    else:
        print("Preview only. Use --send to push to backpack.")


asyncio.run(main())
