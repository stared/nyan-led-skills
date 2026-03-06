"""RPG Shop — pixel art wares cycling in a shop window display.

Browse swords, potions, shields, and gems at ye olde pixel shoppe.

Usage:
  uv run scripts/rpg_shop.py
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

# Pixel art items (each row is a string, mapped via color palette)
SWORD = {
    "art": [
        "......yy......",
        "......WW......",
        "......WW......",
        "......WW......",
        "......WW......",
        "......WW......",
        "......WW......",
        "..bb.WWWW.bb..",
        "...bBBWWBBb...",
        "....bBWWBb....",
        ".....brrb.....",
        "......rr......",
        "......GG......",
        "......yy......",
    ],
    "palette": {
        "W": (200, 210, 220),  # blade silver
        "B": (140, 100, 60),   # crossguard brown
        "b": (100, 70, 40),    # dark brown
        "r": (120, 60, 30),    # grip leather
        "G": (180, 160, 50),   # pommel gold
        "y": (255, 220, 80),   # gold shine
    },
}

POTION = {
    "art": [
        "......WW......",
        ".....WWWW.....",
        "......WW......",
        "....GGGGGG....",
        "...GrrrrrrG...",
        "..GrrRRRRrrG..",
        "..GrrRRRRrrG..",
        "..GrrRRRRrrG..",
        "..GrrRRRRrrG..",
        "..GrrrrrrrrG..",
        "...GrrrrrrG...",
        "....GGGGGG....",
    ],
    "palette": {
        "W": (200, 200, 210),  # cork
        "G": (100, 160, 100),  # glass green
        "r": (200, 40, 40),    # potion red
        "R": (255, 80, 80),    # potion highlight
    },
}

SHIELD = {
    "art": [
        "..GGGGGGGGGG..",
        ".GBBBBbbBBBBG.",
        ".GBBBBbbBBBBG.",
        ".GBBGGggGGBBG.",
        ".GBBgBBBBgBBG.",
        ".GBBBBbbBBBBG.",
        ".GBBBBbbBBBBG.",
        "..GBBBbbBBBG..",
        "...GBBbbBBG...",
        "....GBbbBG....",
        ".....GbbG.....",
        "......GG......",
    ],
    "palette": {
        "G": (200, 180, 60),   # gold trim
        "g": (170, 150, 40),   # dark gold
        "B": (50, 80, 180),    # shield blue
        "b": (70, 100, 200),   # shield light blue
    },
}

GEM = {
    "art": [
        "......GG......",
        "....GGEEGG....",
        "...GEEeeEEG...",
        "..GEEeEEeEEG..",
        "..GEeEEEEeEG..",
        "..GEEeEEeEEG..",
        "...GEEeeEEG...",
        "....GGEEGG....",
        ".....GEEG.....",
        "......GG......",
    ],
    "palette": {
        "G": (180, 140, 220),  # facet outline purple
        "E": (100, 220, 130),  # emerald green
        "e": (150, 255, 170),  # emerald highlight
    },
}

SCROLL = {
    "art": [
        "...TTTTTTTT...",
        "..TBBBBBBBBt..",
        "..TB......Bt..",
        "...B.llll.B...",
        "...B.llll.B...",
        "...B......B...",
        "...B.llll.B...",
        "...B.llll.B...",
        "...B......B...",
        "..TB......Bt..",
        "..TBBBBBBBBt..",
        "...tttttttt...",
    ],
    "palette": {
        "T": (200, 170, 110),  # scroll roll top
        "t": (160, 130, 80),   # scroll roll shadow
        "B": (230, 210, 170),  # parchment
        "l": (80, 50, 30),     # ink lines
    },
}

WARES = [
    ("Sword", SWORD, "50g", (255, 200, 80)),
    ("Potion", POTION, "15g", (255, 80, 80)),
    ("Shield", SHIELD, "80g", (80, 130, 220)),
    ("Gem", GEM, "200g", (120, 230, 150)),
    ("Scroll", SCROLL, "35g", (210, 190, 140)),
]

# Shop border color
BORDER = (120, 80, 40)     # wood brown
BORDER_HI = (160, 120, 60) # lighter wood


def draw_border(img: Image.Image):
    """Draw a wooden shop window border."""
    for x in range(S):
        for t in range(2):
            c = BORDER_HI if t == 0 else BORDER
            img.putpixel((x, t), c)
            img.putpixel((x, S - 1 - t), c)
            img.putpixel((t, x), c)
            img.putpixel((S - 1 - t, x), c)


def draw_art(img: Image.Image, art: list[str], palette: dict, cx: int, cy: int):
    """Draw pixel art centered at (cx, cy)."""
    h = len(art)
    w = len(art[0]) if art else 0
    ox = cx - w // 2
    oy = cy - h // 2
    for row_idx, row in enumerate(art):
        for col_idx, ch in enumerate(row):
            color = palette.get(ch)
            if color:
                px, py = ox + col_idx, oy + row_idx
                if 0 <= px < S and 0 <= py < S:
                    img.putpixel((px, py), color)


def draw_text(img: Image.Image, text: str, cx: int, cy: int, color):
    """Draw centered text in a single color."""
    char_w, char_h, spacing = 5, 7, 1
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
                    px, py = x + col, y + row
                    if 0 <= px < S and 0 <= py < S:
                        img.putpixel((px, py), color)
        x += char_w + spacing


def draw_coins(img: Image.Image, cx: int, cy: int):
    """Draw a tiny gold coin icon."""
    coin = [
        ".yGy.",
        "yGGGy",
        "GGyGG",
        "yGGGy",
        ".yGy.",
    ]
    palette = {"G": (220, 180, 40), "y": (255, 220, 80)}
    draw_art(img, coin, palette, cx, cy)


def generate_frames() -> list[Image.Image]:
    frames = []
    cx = S // 2

    for name, item, price, name_color in WARES:
        img = Image.new("RGB", (S, S), (15, 10, 25))  # dark purple-black bg

        draw_border(img)

        # Item name at top
        draw_text(img, name, cx, 9, name_color)

        # Pixel art item in center
        draw_art(img, item["art"], item["palette"], cx, 32)

        # Price at bottom with coin
        draw_coins(img, cx - 14, 54)
        draw_text(img, price, cx + 2, 54, (255, 220, 80))

        frames.append(img)

        # Second frame: same item with a sparkle/shine
        img2 = img.copy()
        # Add sparkle dots around the item
        sparkles = [(cx - 12, 26), (cx + 11, 28), (cx - 8, 38),
                     (cx + 10, 36), (cx, 22), (cx + 6, 40)]
        for sx, sy in sparkles:
            if 0 <= sx < S and 0 <= sy < S:
                img2.putpixel((sx, sy), (255, 255, 220))
        frames.append(img2)

    return frames


def make_animated_gif(frames: list[Image.Image], durations: list[int]) -> bytes:
    quantized = [
        f.convert("RGB").quantize(colors=48).convert("RGB")
        for f in frames
    ]
    buf = BytesIO()
    quantized[0].save(
        buf, format="GIF", save_all=True,
        append_images=quantized[1:], duration=durations, loop=0,
    )
    return buf.getvalue()


async def main():
    print("Generating RPG shop animation...")
    frames = generate_frames()

    # Each item: 700ms display, 300ms with sparkle, then next item
    durations = [700, 300] * len(WARES)

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

    print("Done! Welcome to the shop.")


asyncio.run(main())
