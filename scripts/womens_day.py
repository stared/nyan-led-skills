"""Women's Day animation — tulips, hearts, and warm wishes.

Six looping scenes with floating hearts, bouncy text, pixel-art tulip,
and a sparkly "Dzien Kobiet!" message. Use --for to personalize.

Usage:
  uv run scripts/ola_womens_day.py                  # generic hearts
  uv run scripts/ola_womens_day.py --for Ola         # personalized
  uv run scripts/ola_womens_day.py --preview         # save preview GIF
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

S = DISPLAY_SIZE
CHUNK_SIZE = 196
FINALIZE = make_cmd(0x000F, 0x3603, b"\x01\x00\x00")

# ── Color palette ──────────────────────────────────────────────────
PINK = (255, 100, 150)
HOT_PINK = (255, 50, 120)
MAGENTA = (220, 40, 130)
LIGHT_PINK = (255, 180, 200)
RED = (255, 60, 80)
CREAM = (255, 240, 220)
STEM_GREEN = (60, 180, 80)
LEAF_GREEN = (40, 130, 55)
BG = (15, 5, 15)  # dark warm background

PINK_RAINBOW = [PINK, HOT_PINK, MAGENTA, LIGHT_PINK, RED, (255, 130, 170), (240, 80, 140)]

# ── Pixel art ──────────────────────────────────────────────────────

TULIP_ART = [
    ".....rrrr.....",
    "....rRRRRr....",
    "...rRRRRRRr...",
    "..rRRRppRRRr..",
    "..RRpRRRRpRR..",
    "..rRRRRRRRRr..",
    "...rRRRRRRr...",
    "....rrrrr.....",
    "......gg......",
    "......gg......",
    ".....ggg......",
    "....gGgg......",
    "...gG..gg.....",
    "..gG....gg....",
]

TULIP_PALETTE = {
    "r": RED,
    "R": HOT_PINK,
    "p": PINK,
    "g": STEM_GREEN,
    "G": LEAF_GREEN,
}

SMALL_HEART = [
    ".r.r.",
    "rrrrr",
    ".rrr.",
    "..r..",
]

# ── Floating hearts system ─────────────────────────────────────────

HEART_COLORS = [PINK, HOT_PINK, MAGENTA, RED, LIGHT_PINK, (255, 80, 130)]

random.seed(42)
HEARTS = [
    {
        "x": random.randint(2, S - 7),
        "y_base": random.randint(0, S - 1),
        "speed": random.uniform(1.0, 3.0),
        "phase": random.uniform(0, 2 * math.pi),
        "color_idx": random.randint(0, len(HEART_COLORS) - 1),
    }
    for _ in range(15)
]


# ── Drawing helpers ────────────────────────────────────────────────

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


def draw_text(img: Image.Image, text: str, cx: int, cy: int,
              color: tuple[int, int, int], scale: int = 1):
    """Draw text centered at (cx, cy) in a single color."""
    spacing = scale
    tw = text_width(text, scale, spacing)
    x = cx - tw // 2
    char_h = 7 * scale
    y = cy - char_h // 2
    char_w = 5 * scale
    for ch in text:
        if ch == " ":
            x += char_w + spacing
            continue
        draw_glyph(img, ch, x, y, color, scale)
        x += char_w + spacing


def draw_wavy_line(img: Image.Image, text: str, cx: int, cy: int,
                   frame: int, num_frames: int, color_offset: int = 0,
                   scale: int = 1, wave_amp: float = 3.0, wave_speed: float = 1.0):
    """Draw text with per-letter sine wave bounce and pink rainbow colors."""
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
        dy = int(wave_amp * math.sin(t * wave_speed + i * 0.8))
        color = PINK_RAINBOW[(i + color_offset) % len(PINK_RAINBOW)]
        draw_glyph(img, ch, x, cy - char_h // 2 + dy, color, scale)
        x += char_w + spacing


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


def draw_small_heart(img: Image.Image, cx: int, cy: int, color: tuple[int, int, int]):
    """Draw a 5x4 heart centered at (cx, cy)."""
    palette = {"r": color}
    draw_art(img, SMALL_HEART, palette, cx, cy)


def draw_floating_hearts(img: Image.Image, frame: int):
    """Draw floating hearts that drift upward and wrap around."""
    for h in HEARTS:
        y = (h["y_base"] - int(frame * h["speed"])) % S
        x = h["x"] + int(2 * math.sin(frame * 0.4 + h["phase"]))
        x = x % S
        bright = math.sin(frame * 0.5 + h["phase"]) * 0.3 + 0.7
        color = HEART_COLORS[h["color_idx"]]
        c = tuple(int(v * bright) for v in color)
        draw_small_heart(img, x, y, c)


def draw_sparkles(img: Image.Image, frame: int, positions: list[tuple[int, int]]):
    """Draw twinkling sparkle dots at given positions."""
    for i, (sx, sy) in enumerate(positions):
        bright = math.sin(frame * 1.2 + i * 1.5) * 0.5 + 0.5
        if bright > 0.3:
            c = tuple(int(255 * bright) for _ in range(3))
            if 0 <= sx < S and 0 <= sy < S:
                img.putpixel((sx, sy), c)
                # Cross sparkle shape
                for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                    nx, ny = sx + dx, sy + dy
                    if 0 <= nx < S and 0 <= ny < S:
                        dim = tuple(int(200 * bright) for _ in range(3))
                        img.putpixel((nx, ny), dim)


# ── Scene generators ───────────────────────────────────────────────

def scene_floating_hearts(num_sub: int = 4) -> list[Image.Image]:
    """Scene 1: Floating hearts intro (800ms)."""
    frames = []
    for f in range(num_sub):
        img = Image.new("RGB", (S, S), BG)
        draw_floating_hearts(img, f * 2)
        frames.append(img)
    return frames


def scene_name_bouncy(name: str, num_sub: int = 6) -> list[Image.Image]:
    """Scene 2: Name big & bouncy, or just hearts if no name (1200ms)."""
    frames = []
    cx = S // 2
    for f in range(num_sub):
        img = Image.new("RGB", (S, S), BG)
        draw_floating_hearts(img, f * 2 + 10)
        if name:
            scale = 2 if len(name) <= 5 else 1
            draw_wavy_line(img, name, cx, S // 2, f, num_sub,
                           color_offset=f, scale=scale, wave_amp=4, wave_speed=1.5)
        frames.append(img)
    return frames


def scene_tulip_with_name(name: str, num_sub: int = 2) -> list[Image.Image]:
    """Scene 3: Tulip pixel art + name at top if provided (1500ms)."""
    frames = []
    cx = S // 2
    for f in range(num_sub):
        img = Image.new("RGB", (S, S), BG)
        if name:
            draw_text(img, name, cx, 8, LIGHT_PINK)
        draw_art(img, TULIP_ART, TULIP_PALETTE, cx, 35)
        frames.append(img)
    return frames


def scene_dzien_kobiet(num_sub: int = 2) -> list[Image.Image]:
    """Scene 4: Tulip + 'Dzien Kobiet!' text (1500ms)."""
    frames = []
    cx = S // 2
    for f in range(num_sub):
        img = Image.new("RGB", (S, S), BG)
        # Tulip higher up
        draw_art(img, TULIP_ART, TULIP_PALETTE, cx, 24)
        # "Dzien" and "Kobiet!" below tulip
        draw_text(img, "Dzien", cx, 44, CREAM)
        draw_text(img, "Kobiet!", cx, 55, PINK)
        frames.append(img)
    return frames


def scene_sparkle_frame(num_sub: int = 4) -> list[Image.Image]:
    """Scene 5: Same as scene 4 + sparkles and hearts (1000ms)."""
    frames = []
    cx = S // 2
    sparkle_positions = [
        (cx - 14, 14), (cx + 13, 16), (cx - 10, 28), (cx + 12, 26),
        (cx - 6, 10), (cx + 8, 32), (cx, 8), (cx - 12, 32),
        (cx + 6, 12), (cx - 4, 34), (cx + 10, 20), (cx - 8, 20),
    ]
    for f in range(num_sub):
        img = Image.new("RGB", (S, S), BG)
        draw_floating_hearts(img, f * 3 + 20)
        draw_art(img, TULIP_ART, TULIP_PALETTE, cx, 24)
        draw_text(img, "Dzien", cx, 44, CREAM)
        draw_text(img, "Kobiet!", cx, 55, PINK)
        draw_sparkles(img, f * 3, sparkle_positions)
        frames.append(img)
    return frames


def scene_hearts_finale(name: str, num_sub: int = 4) -> list[Image.Image]:
    """Scene 6: 'Name <3' text + heart shower (1000ms)."""
    frames = []
    cx = S // 2
    label = f"{name} <3" if name else "<3"
    for f in range(num_sub):
        img = Image.new("RGB", (S, S), BG)
        draw_floating_hearts(img, f * 3 + 30)
        draw_wavy_line(img, label, cx, S // 2, f, num_sub,
                       color_offset=f, scale=1, wave_amp=3, wave_speed=1.2)
        draw_small_heart(img, 8, 8, HOT_PINK)
        draw_small_heart(img, S - 8, 8, PINK)
        draw_small_heart(img, 8, S - 8, MAGENTA)
        draw_small_heart(img, S - 8, S - 8, RED)
        frames.append(img)
    return frames


# ── Frame assembly ─────────────────────────────────────────────────

def generate_frames(name: str = "") -> tuple[list[Image.Image], list[int]]:
    """Generate all frames with per-frame durations."""
    scenes = [
        (lambda: scene_floating_hearts(), 800),
        (lambda: scene_name_bouncy(name), 1200),
        (lambda: scene_tulip_with_name(name), 1500),
        (lambda: scene_dzien_kobiet(), 1500),
        (lambda: scene_sparkle_frame(), 1000),
        (lambda: scene_hearts_finale(name), 1000),
    ]

    all_frames = []
    all_durations = []

    for gen_fn, total_ms in scenes:
        scene_frames = gen_fn()
        per_frame_ms = total_ms // len(scene_frames)
        all_frames.extend(scene_frames)
        all_durations.extend([per_frame_ms] * len(scene_frames))

    return all_frames, all_durations


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
    preview = "--preview" in sys.argv
    name = ""
    if "--for" in sys.argv:
        idx = sys.argv.index("--for")
        if idx + 1 < len(sys.argv):
            name = sys.argv[idx + 1]

    label = f" for {name}" if name else ""
    print(f"Generating Women's Day animation{label}...")
    frames, durations = generate_frames(name)

    gif_data = make_animated_gif(frames, durations)
    num_chunks = (len(gif_data) + CHUNK_SIZE - 1) // CHUNK_SIZE
    print(f"Animated GIF: {len(frames)} frames, {len(gif_data)} bytes, {num_chunks} chunks")

    if num_chunks > 255:
        print(f"ERROR: {num_chunks} chunks exceeds protocol limit of 255.")
        return

    if preview:
        out = Path(__file__).parent / "womens_day_preview.gif"
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

    msg = f"Done! Happy Women's Day, {name}!" if name else "Done! Happy Women's Day!"
    print(msg)


asyncio.run(main())
