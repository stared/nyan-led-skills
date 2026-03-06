"""TELEGAZETA — AI news in classic Polish teletext style.

Blue background, red header bar, yellow headlines. Just like the 90s,
but the news is from March 2026.

Usage:
  uv run scripts/telegazeta.py
"""

import asyncio
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

# Teletext color palette
BG = (0, 0, 140)           # classic teletext blue
HEADER_BG = (180, 20, 20)  # red header bar
WHITE = (255, 255, 255)
YELLOW = (255, 255, 40)
CYAN = (80, 255, 255)
GREEN = (40, 255, 40)
SEPARATOR = (200, 200, 200)

# News pages: (header_text, lines, line_colors)
PAGES = [
    (
        "100",
        ["TELE", "GAZETA", "", "MODELS!", "Mar 2026"],
        [WHITE, WHITE, None, YELLOW, CYAN],
    ),
    (
        "101",
        ["Claude", "Opus 4.6", "Feb 5"],
        [YELLOW, WHITE, CYAN],
    ),
    (
        "102",
        ["GPT-5.3", "Codex", "Feb 5"],
        [YELLOW, WHITE, CYAN],
    ),
    (
        "103",
        ["Gemini", "3.1 Pro", "1M ctx!"],
        [YELLOW, WHITE, GREEN],
    ),
    (
        "104",
        ["Grok 4.20", "4 agents", "inside!"],
        [YELLOW, WHITE, GREEN],
    ),
    (
        "105",
        ["DeepSeek", "V4: 1T", "params!"],
        [YELLOW, WHITE, GREEN],
    ),
    (
        "106",
        ["Qwen 3.5", "Seed 2.0", "GLM-5"],
        [YELLOW, WHITE, CYAN],
    ),
    (
        "107",
        ["12 models", "in Feb!", "AI race!"],
        [YELLOW, WHITE, GREEN],
    ),
]


def draw_text(img: Image.Image, text: str, x: int, y: int, color, align="left"):
    """Draw text at pixel position. align='center' centers at x."""
    char_w, char_h, spacing = 5, 7, 1
    total_w = len(text) * char_w + (len(text) - 1) * spacing

    if align == "center":
        x = x - total_w // 2
    elif align == "right":
        x = x - total_w

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
                        img.putpixel((px, py), color)
        x += char_w + spacing


def draw_header_bar(img: Image.Image, page_num: str):
    """Draw the red header bar with page number."""
    # Red bar across top
    for y in range(0, 11):
        for x in range(S):
            img.putpixel((x, y), HEADER_BG)

    # "AI" on left, page number on right
    draw_text(img, "AI", 2, 2, WHITE)
    draw_text(img, page_num, S - 2, 2, YELLOW, align="right")


def draw_separator(img: Image.Image, y: int):
    """Draw a thin horizontal separator line."""
    for x in range(2, S - 2):
        if x % 2 == 0:  # dashed for teletext feel
            img.putpixel((x, y), SEPARATOR)


def draw_footer(img: Image.Image):
    """Draw colored blocks at bottom — classic teletext footer."""
    colors = [
        (255, 0, 0), (0, 255, 0), (255, 255, 0), (0, 0, 255),
        (255, 0, 255), (0, 255, 255), (255, 255, 255), (0, 0, 0),
    ]
    block_w = S // len(colors)
    for i, color in enumerate(colors):
        for x in range(i * block_w, (i + 1) * block_w):
            for y in range(S - 4, S):
                if 0 <= x < S:
                    img.putpixel((x, y), color)


def generate_frames() -> list[Image.Image]:
    frames = []
    cx = S // 2

    for page_num, lines, colors in PAGES:
        img = Image.new("RGB", (S, S), BG)

        draw_header_bar(img, page_num)
        draw_separator(img, 12)

        # Draw content lines, centered
        y_start = 16
        line_gap = 10  # 7px char + 3px gap

        for i, line in enumerate(lines):
            if not line or i >= len(colors) or colors[i] is None:
                continue
            draw_text(img, line, cx, y_start + i * line_gap, colors[i], align="center")

        draw_footer(img)
        frames.append(img)

    return frames


def make_animated_gif(frames: list[Image.Image], durations: list[int]) -> bytes:
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


async def main():
    print("Generating TELEGAZETA AI news...")
    frames = generate_frames()

    # Title page longer, news pages shorter
    durations = [2000] + [1500] * (len(PAGES) - 1)

    gif_data = make_animated_gif(frames, durations)
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

    print("Done! Tune in to TELEGAZETA.")


asyncio.run(main())
