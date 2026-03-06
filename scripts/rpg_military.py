"""Military surplus shop — COBOL legacy gear now with a nice AI interface.

Pixel art military equipment cycling through a retro terminal-styled shop.

Usage:
  uv run scripts/rpg_military.py
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

# Pixel art military items

TANK = {
    "art": [
        "...............",
        "......GGG......",
        "......GGG......",
        "......GGG......",
        "...GGGGGGGGG...",
        "..GGGDDDDDGGG..",
        "..GDDDDDDDDG..",
        "..GDDDDDDDDG..",
        ".TGDDDDDDDDGT.",
        ".TtTTTTTTTTtT..",
        ".TtTtTtTtTtT...",
        "..ttttttttt....",
    ],
    "palette": {
        "G": (80, 90, 50),     # olive green body
        "D": (60, 70, 40),     # dark green detail
        "T": (90, 85, 60),     # track tan
        "t": (60, 55, 35),     # track shadow
    },
}

RADAR = {
    "art": [
        "......GG......",
        ".....G..G.....",
        "....G....G....",
        "...G......G...",
        "...G..gg..G...",
        "....G.gG.G....",
        ".....GGG......",
        "......GG......",
        "......MM......",
        "......MM......",
        "......MM......",
        "....MMMMMM....",
    ],
    "palette": {
        "G": (40, 180, 40),    # radar green
        "g": (80, 255, 80),    # radar bright sweep
        "M": (100, 100, 110),  # metal base
    },
}

HELMET = {
    "art": [
        "....GGGGGG....",
        "...GGGGGGGG...",
        "..GGGGGGGGGG..",
        "..GGGGGGGGGG..",
        "..GGGGggGGGG..",
        ".GGGGGGGGGGGG.",
        ".GGGGGGGGGGGg.",
        ".gGGGGGGGGGGg.",
        "..gggggggggg..",
    ],
    "palette": {
        "G": (80, 90, 50),     # olive drab
        "g": (55, 60, 35),     # shadow
    },
}

MISSILE = {
    "art": [
        "......RR......",
        ".....RWWR.....",
        ".....RWWR.....",
        "....RWWWWR....",
        "....RGGGWR....",
        "....RGGGWR....",
        "....RGGGWR....",
        "....RGGGWR....",
        "...RRGGGRR....",
        "..FF.GGGG.FF..",
        ".FF..GGGG..FF.",
        ".F...YYYY...F.",
        ".....YOYY.....",
        "......OO......",
    ],
    "palette": {
        "R": (160, 40, 30),    # red nose/body
        "W": (200, 200, 200),  # white tip
        "G": (100, 100, 100),  # gray body
        "F": (80, 80, 90),     # fins
        "Y": (255, 200, 40),   # flame yellow
        "O": (255, 120, 20),   # flame orange
    },
}

RADIO = {
    "art": [
        ".....AA.......",
        "....A.A.......",
        "...A..A.......",
        "..GGGGGGGG....",
        "..GDDDDDDG...",
        "..GDggggDDG...",
        "..GDggggDDG...",
        "..GDDDDDDG...",
        "..GD.BB.DDG...",
        "..GD.BB.DDG...",
        "..GDDDDDDG...",
        "..GGGGGGGG....",
    ],
    "palette": {
        "A": (140, 140, 140),  # antenna
        "G": (60, 70, 45),     # olive case
        "D": (50, 55, 35),     # case dark
        "g": (40, 180, 40),    # screen green
        "B": (80, 80, 70),     # knobs
    },
}

WARES = [
    ("Tank", TANK, "9999g", (80, 90, 50)),
    ("Radar", RADAR, "420g", (40, 200, 40)),
    ("Helmet", HELMET, "65g", (140, 140, 100)),
    ("Missile", MISSILE, "1337g", (200, 60, 40)),
    ("Radio", RADIO, "250g", (100, 160, 80)),
]

BORDER = (30, 50, 30)      # dark military green
BORDER_HI = (50, 80, 50)   # lighter green


def draw_border(img: Image.Image):
    """Draw a military-styled border."""
    for x in range(S):
        for t in range(2):
            c = BORDER_HI if t == 0 else BORDER
            img.putpixel((x, t), c)
            img.putpixel((x, S - 1 - t), c)
            img.putpixel((t, x), c)
            img.putpixel((S - 1 - t, x), c)
    # Corner rivets
    rivet = (120, 120, 100)
    for rx, ry in [(3, 3), (S-4, 3), (3, S-4), (S-4, S-4)]:
        img.putpixel((rx, ry), rivet)


def draw_art(img: Image.Image, art: list[str], palette: dict, cx: int, cy: int):
    h = len(art)
    w = max(len(row) for row in art)
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


def draw_scanline(img: Image.Image, frame: int):
    """Retro CRT scanline sweeping down — the COBOL terminal feel."""
    scan_y = (frame * 8) % S
    for x in range(S):
        if 0 <= scan_y < S:
            r, g, b = img.getpixel((x, scan_y))
            img.putpixel((x, scan_y), (min(r + 40, 255), min(g + 60, 255), min(b + 40, 255)))


def generate_frames() -> list[Image.Image]:
    frames = []
    cx = S // 2

    for item_idx, (name, item, price, name_color) in enumerate(WARES):
        # Two frames per item: normal + scanline sweep
        for sub in range(2):
            img = Image.new("RGB", (S, S), (8, 12, 8))  # very dark green bg

            draw_border(img)

            # Item name at top in military green-ish
            draw_text(img, name, cx, 9, name_color)

            # Pixel art item in center
            draw_art(img, item["art"], item["palette"], cx, 31)

            # Price at bottom
            draw_text(img, price, cx, 54, (200, 180, 60))

            # Scanline effect on second sub-frame
            if sub == 1:
                draw_scanline(img, item_idx * 3)

            frames.append(img)

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
    print("Generating military surplus shop...")
    frames = generate_frames()

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

    print("Done! COBOL-to-AI upgrade complete.")


asyncio.run(main())
