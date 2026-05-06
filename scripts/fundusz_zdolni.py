"""Fundusz Zdolni — Falenty 2026 animation for the Nyan Gear LED backpack.

Curiosity-themed animation for Fundusz ZDOLNI (formerly Krajowy Fundusz na
rzecz Dzieci, KFnrD; 1981-2024). The flagship event is a ~10-day general
scientific camp in Falenty bringing together Polish high-school scholarship
holders across mathematics, physics, chemistry, biology, music, and the
humanities. Motto: "Budzimy ciekawosc!" (We awaken curiosity!).

The animation rotates a spotlight across five discipline icons on a starry
sky, under "FUNDUSZ ZDOLNI" branding with "FALENTY 2026" subtitle and a
scrolling motto.

Usage:
  uv run scripts/fundusz_zdolni.py             # send to backpack
  uv run scripts/fundusz_zdolni.py --preview   # save preview GIF
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

# ── Palette ──────────────────────────────────────────────────────
BG_TOP = (3, 6, 24)
BG_BOT = (10, 18, 50)

FZ_BLUE = (60, 140, 235)
FZ_LIGHT = (170, 215, 255)
WHITE = (245, 245, 255)
GOLD = (255, 205, 70)
CYAN = (90, 220, 240)

# Disciplines: math, physics, chemistry, biology, music
DISC_COLORS = [
    (90, 230, 220),   # math   — cyan
    (255, 220, 80),   # physics — yellow
    (110, 240, 140),  # chemistry — green
    (255, 130, 200),  # biology — pink
    (200, 140, 255),  # music — violet
]

# ── Pixel-art icons (5x7) ────────────────────────────────────────
ICON_PI = [
    ".....",
    "#####",
    ".#.#.",
    ".#.#.",
    ".#.#.",
    "##.##",
    "#...#",
]

ICON_ATOM = [
    "..#..",
    ".###.",
    "#...#",
    "#.#.#",
    "#...#",
    ".###.",
    "..#..",
]

ICON_FLASK = [
    ".###.",
    "..#..",
    "..#..",
    ".###.",
    ".###.",
    "#####",
    ".###.",
]

ICON_DNA = [
    "#...#",
    ".#.#.",
    "..#..",
    ".#.#.",
    "#...#",
    ".#.#.",
    "..#..",
]

ICON_NOTE = [
    "..###",
    "..#.#",
    "..#..",
    "..#..",
    "..#..",
    "###..",
    "##...",
]

ICONS = [ICON_PI, ICON_ATOM, ICON_FLASK, ICON_DNA, ICON_NOTE]
ICON_CENTERS_X = [7, 20, 32, 44, 57]


def lerp_color(c1, c2, t):
    return tuple(int(a + (b - a) * t) for a, b in zip(c1, c2))


def dim(color, factor):
    return tuple(int(c * factor) for c in color)


def add_pixel(img, x, y, color):
    if 0 <= x < S and 0 <= y < S:
        old = img.getpixel((x, y))
        img.putpixel(
            (x, y),
            (
                min(255, old[0] + color[0]),
                min(255, old[1] + color[1]),
                min(255, old[2] + color[2]),
            ),
        )


def draw_sky(img, frame):
    """Vertical gradient: deep navy top -> slightly bluer bottom."""
    for y in range(S):
        t = y / (S - 1)
        col = lerp_color(BG_TOP, BG_BOT, t)
        for x in range(S):
            img.putpixel((x, y), col)


def draw_stars(img, frame):
    """Twinkling stars across the whole canvas (avoids text rows)."""
    rng = random.Random(1981)  # KFnrD founding year
    text_rows = set()
    text_rows.update(range(1, 8))     # FUNDUSZ
    text_rows.update(range(9, 16))    # ZDOLNI
    text_rows.update(range(33, 40))   # FALENTY
    text_rows.update(range(41, 48))   # 2026
    text_rows.update(range(54, 61))   # motto

    for _ in range(45):
        sx = rng.randint(0, S - 1)
        sy = rng.randint(0, S - 1)
        if sy in text_rows:
            continue
        phase = rng.random() * 10
        base = rng.uniform(0.25, 1.0)
        twinkle = math.sin(frame * 0.7 + phase) * 0.45 + 0.55
        v = int(120 * base * twinkle)
        if v < 12:
            continue
        # Slightly cool tint for stars
        add_pixel(img, sx, sy, (v, v, min(255, int(v * 1.15))))


def draw_text(img, text, cx, y, color, frame=0, shimmer=0.0):
    """Render text using PIXEL_FONT_5x7, centered on cx."""
    char_w, spacing = 5, 1
    total_w = len(text) * char_w + (len(text) - 1) * spacing
    x = cx - total_w // 2
    for i, ch in enumerate(text):
        glyph = PIXEL_FONT_5x7.get(ch)
        if glyph is None or ch == " ":
            x += char_w + spacing
            continue
        if shimmer > 0:
            wave = math.sin(frame * 0.9 + i * 0.6) * shimmer
            ch_color = tuple(
                max(0, min(255, int(v * (1 + wave))))
                for v in color
            )
        else:
            ch_color = color
        for row in range(7):
            for col in range(char_w):
                if glyph[row] & (1 << (char_w - 1 - col)):
                    px, py = x + col, y + row
                    if 0 <= px < S and 0 <= py < S:
                        img.putpixel((px, py), ch_color)
        x += char_w + spacing


def draw_text_gradient(img, text, cx, y, c_start, c_end, frame=0):
    """Render text with a left-to-right color gradient and subtle shimmer."""
    char_w, spacing = 5, 1
    total_w = len(text) * char_w + (len(text) - 1) * spacing
    x = cx - total_w // 2
    n = max(1, len(text) - 1)
    for i, ch in enumerate(text):
        glyph = PIXEL_FONT_5x7.get(ch)
        if glyph is None or ch == " ":
            x += char_w + spacing
            continue
        t = i / n
        shimmer = math.sin(frame * 0.7 + i * 0.5) * 0.12
        t = max(0, min(1, t + shimmer))
        color = lerp_color(c_start, c_end, t)
        for row in range(7):
            for col in range(char_w):
                if glyph[row] & (1 << (char_w - 1 - col)):
                    px, py = x + col, y + row
                    if 0 <= px < S and 0 <= py < S:
                        img.putpixel((px, py), color)
        x += char_w + spacing


def draw_icon(img, icon, cx, top_y, color, brightness=1.0):
    """Render a 5x7 pixel-art icon centered horizontally on cx."""
    h = len(icon)
    w = len(icon[0])
    x0 = cx - w // 2
    c = tuple(int(v * brightness) for v in color)
    for row in range(h):
        for col in range(w):
            if icon[row][col] == "#":
                px, py = x0 + col, top_y + row
                if 0 <= px < S and 0 <= py < S:
                    img.putpixel((px, py), c)


def draw_icons_row(img, frame):
    """Five discipline icons; the active one is brighter and gets a halo."""
    active = (frame // 2) % len(ICONS)
    icon_top_y = 19
    pulse = 0.85 + 0.15 * math.sin(frame * 1.2)

    for i, (icon, cx, color) in enumerate(zip(ICONS, ICON_CENTERS_X, DISC_COLORS)):
        if i == active:
            # Halo: subtle ring of dim color around the icon
            halo = dim(color, 0.35)
            for dx, dy in [
                (-4, 3), (4, 3),
                (-4, 0), (4, 0),
                (-4, -3), (4, -3),
                (0, -2), (0, 8),
            ]:
                add_pixel(img, cx + dx, icon_top_y + dy, halo)
            draw_icon(img, icon, cx, icon_top_y, color, brightness=pulse)
            # Bright sparkle above active icon
            spark_y = icon_top_y - 3
            if frame % 2 == 0:
                add_pixel(img, cx, spark_y, GOLD)
                add_pixel(img, cx - 1, spark_y + 1, dim(GOLD, 0.5))
                add_pixel(img, cx + 1, spark_y + 1, dim(GOLD, 0.5))
            else:
                add_pixel(img, cx, spark_y + 1, dim(GOLD, 0.7))
        else:
            draw_icon(img, icon, cx, icon_top_y, color, brightness=0.32)


def draw_scrolling_motto(img, frame, y):
    """Scroll the motto BUDZIMY CIEKAWOSC! across the bottom."""
    text = "BUDZIMY CIEKAWOSC!     "
    char_w, spacing = 5, 1
    cell_w = char_w + spacing
    total_w = len(text) * cell_w
    offset = int(frame * total_w / NUM_FRAMES) % total_w
    pulse = 0.85 + 0.15 * math.sin(frame * 0.6)
    base = tuple(int(v * pulse) for v in GOLD)

    for repeat in range(2):
        for i, ch in enumerate(text):
            x_start = repeat * total_w + i * cell_w - offset
            if x_start + char_w < 0 or x_start >= S:
                continue
            glyph = PIXEL_FONT_5x7.get(ch)
            if glyph is None or ch == " ":
                continue
            for row in range(7):
                for col in range(char_w):
                    if glyph[row] & (1 << (char_w - 1 - col)):
                        px, py = x_start + col, y + row
                        if 0 <= px < S and 0 <= py < S:
                            img.putpixel((px, py), base)


def draw_shooting_star(img, frame):
    """One occasional shooting star streaking across the top."""
    if frame < 3 or frame > 6:
        return
    progress = (frame - 3) / 3
    head_x = int(8 + progress * 50)
    head_y = int(4 + progress * 3)
    # Trail
    for k in range(5):
        tx = head_x - k
        ty = head_y - k // 2
        v = int(220 * (1 - k / 5))
        add_pixel(img, tx, ty, (v, v, min(255, int(v * 1.1))))
    # Bright head
    add_pixel(img, head_x, head_y, (255, 255, 255))


def draw_corner_sparkles(img, frame):
    """Tiny gold sparkles in the corners that pop in/out."""
    spots = [(2, 17), (61, 17), (2, 30), (61, 30), (2, 50), (61, 50)]
    for i, (x, y) in enumerate(spots):
        phase = i * 0.9
        v = math.sin(frame * 0.8 + phase) * 0.5 + 0.5
        if v > 0.65:
            add_pixel(img, x, y, dim(GOLD, v))


def generate_frames():
    frames = []
    cx = S // 2

    for f in range(NUM_FRAMES):
        img = Image.new("RGB", (S, S), BG_TOP)

        draw_sky(img, f)
        draw_stars(img, f)
        draw_shooting_star(img, f)
        draw_corner_sparkles(img, f)

        # Title
        draw_text(img, "FUNDUSZ", cx, 1, WHITE, frame=f, shimmer=0.08)
        draw_text_gradient(img, "ZDOLNI", cx, 9, FZ_LIGHT, FZ_BLUE, frame=f)

        # Discipline icons
        draw_icons_row(img, f)

        # Subtitle
        draw_text(img, "FALENTY", cx, 33, CYAN, frame=f, shimmer=0.05)
        draw_text(img, "2026", cx, 41, WHITE)

        # Scrolling motto
        draw_scrolling_motto(img, f, y=54)

        frames.append(img)

    return frames


def make_animated_gif(frames, duration_ms):
    quantized = [
        f.convert("RGB").quantize(colors=64).convert("RGB") for f in frames
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

    print("Generating Fundusz Zdolni / Falenty 2026...")
    frames = generate_frames()

    gif_data = make_animated_gif(frames, 350)
    num_chunks = (len(gif_data) + CHUNK_SIZE - 1) // CHUNK_SIZE
    print(f"Animated GIF: {len(frames)} frames, {len(gif_data)} bytes, {num_chunks} chunks")

    if num_chunks > 255:
        print(f"ERROR: {num_chunks} chunks exceeds protocol limit.")
        return

    if preview:
        out = Path(__file__).parent / "fundusz_zdolni_preview.gif"
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

    print("Done! Fundusz Zdolni / Falenty 2026 is on display.")


asyncio.run(main())
