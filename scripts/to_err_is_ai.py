"""To Err is AI — K3 Sessions animation for the Nyan Gear LED backpack.

Blue-grid aesthetic matching the K3 Sessions poster. Shows the event
tagline "To err is human AI" with animated strikethrough, a robot face
that errors out, and Quesma + K3 branding.

Usage:
  uv run scripts/to_err_is_ai.py            # send to backpack
  uv run scripts/to_err_is_ai.py --preview   # save preview GIF
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

# ── Colors — matching K3 Sessions poster + Quesma branding ───────
BLUE_BG = (75, 90, 175)
BLUE_GRID = (100, 115, 200)
WHITE = (240, 240, 240)
RED_STRIKE = (220, 60, 70)
BLACK_BG = (8, 8, 16)

# ── Robot pixel art (14 wide x 12 tall) ──────────────────────────
ROBOT_ART = [
    "....aa..aa....",
    "..HHHHHHHHHH..",
    ".HHHHHHHHHHHH.",
    "HH..........HH",
    "HH..EE..EE..HH",
    "HH..EP..PE..HH",
    "HH..EE..EE..HH",
    "HH..........HH",
    "HH..MMMMMM..HH",
    "HH..........HH",
    ".HHHHHHHHHHHH.",
    "..HHHHHHHHHH..",
]

ROBOT_COLORS = {
    "H": (150, 160, 195),
    "E": (190, 200, 235),
    "P": (255, 255, 255),
    "M": (100, 200, 140),
    "a": (120, 130, 165),
}

ROBOT_ERR = {
    "H": (140, 100, 110),
    "E": (230, 70, 70),
    "P": (255, 100, 100),
    "M": (230, 60, 60),
    "a": (120, 90, 100),
}


# ── Drawing helpers ───────────────────────────────────────────────

def draw_glyph(img, ch, x, y, color, scale=1):
    """Draw a single bitmap font character at (x, y) top-left."""
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


def text_width(text, scale=1):
    spacing = scale
    return len(text) * 5 * scale + max(0, len(text) - 1) * spacing


def draw_text_centered(img, text, cx, y, color, scale=1):
    """Draw text centered horizontally at cx."""
    tw = text_width(text, scale)
    draw_text_at(img, text, cx - tw // 2, y, color, scale)


def draw_text_at(img, text, x, y, color, scale=1):
    """Draw text left-aligned starting at (x, y)."""
    spacing = scale
    char_w = 5 * scale
    for ch in text:
        if ch == " ":
            x += char_w + spacing
            continue
        draw_glyph(img, ch, x, y, color, scale)
        x += char_w + spacing


def draw_grid(img):
    """Draw subtle grid pattern on blue background."""
    for i in range(0, S, 8):
        for x in range(S):
            img.putpixel((x, i), BLUE_GRID)
        for y in range(S):
            img.putpixel((i, y), BLUE_GRID)


def draw_art(img, art, palette, cx, cy):
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


def apply_scanline_glitch(img, frame, num_lines=3):
    """Shift random horizontal scanlines left/right."""
    random.seed(frame * 31 + 7)
    for _ in range(num_lines):
        y = random.randint(0, S - 1)
        shift = random.choice([-4, -3, -2, 2, 3, 4])
        row = [img.getpixel((x, y)) for x in range(S)]
        for x in range(S):
            src = x - shift
            img.putpixel((x, y), row[src] if 0 <= src < S else BLUE_BG)


def draw_noise(img, frame, density=0.015):
    """Scatter random bright noise pixels."""
    random.seed(frame * 77 + 3)
    colors = [WHITE, RED_STRIKE, BLUE_GRID, (200, 200, 240)]
    for _ in range(int(S * S * density)):
        x = random.randint(0, S - 1)
        y = random.randint(0, S - 1)
        color = random.choice(colors)
        bright = random.uniform(0.4, 0.8)
        img.putpixel((x, y), tuple(int(v * bright) for v in color))


def draw_sparkles(img, frame):
    """Twinkling sparkle dots."""
    random.seed(99)
    for _ in range(10):
        sx = random.randint(4, S - 5)
        sy = random.randint(4, S - 5)
        phase = random.random() * 10
        bright = math.sin(frame * 0.9 + phase) * 0.5 + 0.5
        if bright > 0.35:
            v = int(180 * bright)
            img.putpixel((sx, sy), (v, v, min(255, int(v * 1.1))))


# ── Scenes ────────────────────────────────────────────────────────

def scene_title(num_frames=8):
    """'To err is human AI' on blue grid with animated strikethrough."""
    frames = []
    cx = S // 2
    char_step = 5 + 1  # char_w + spacing

    # Layout for "human AI" — pre-compute positions
    human_ai_w = text_width("human AI")
    base_x = cx - human_ai_w // 2
    human_w = text_width("human")
    ai_x = base_x + 6 * char_step  # after 5 chars of "human" + space
    text_y = 36
    strike_y = text_y + 3

    for f in range(num_frames):
        img = Image.new("RGB", (S, S), BLUE_BG)
        draw_grid(img)

        # "To err is" — always visible
        draw_text_centered(img, "To err is", cx, 20, WHITE)

        # "human" — always visible
        draw_text_at(img, "human", base_x, text_y, WHITE)

        # Strikethrough: partial on frame 2, full on frame 3+
        if f == 2:
            for x in range(base_x - 1, base_x + human_w // 2):
                if 0 <= x < S:
                    img.putpixel((x, strike_y), RED_STRIKE)
        elif f >= 3:
            for x in range(base_x - 1, base_x + human_w + 1):
                if 0 <= x < S:
                    img.putpixel((x, strike_y), RED_STRIKE)

        # "AI" appears from frame 3+, with subtle pulse
        if f >= 3:
            pulse = 0.88 + 0.12 * math.sin((f - 3) * 1.2)
            ai_color = tuple(max(0, min(255, int(v * pulse))) for v in WHITE)
            draw_text_at(img, "AI", ai_x, text_y, ai_color)

        frames.append(img)
    return frames


def scene_robot(num_frames=4):
    """Robot face on blue grid — normal then error state."""
    frames = []
    cx = S // 2
    for f in range(num_frames):
        img = Image.new("RGB", (S, S), BLUE_BG)
        draw_grid(img)

        if f < 2:
            draw_art(img, ROBOT_ART, ROBOT_COLORS, cx, 24)
            draw_text_centered(img, "hi!", cx, 48, WHITE)
        else:
            draw_art(img, ROBOT_ART, ROBOT_ERR, cx, 24)
            draw_text_centered(img, "oops", cx, 48, RED_STRIKE)
            draw_noise(img, f)
            apply_scanline_glitch(img, f + 20, num_lines=4)

        frames.append(img)
    return frames


def scene_branding(num_frames=4):
    """K3 + QUESMA branding — white on black, matching Quesma logo."""
    frames = []
    cx = S // 2
    for f in range(num_frames):
        img = Image.new("RGB", (S, S), BLACK_BG)
        draw_text_centered(img, "K3", cx, 18, WHITE, scale=2)
        draw_text_centered(img, "QUESMA", cx, 40, WHITE)
        draw_sparkles(img, f)
        frames.append(img)
    return frames


# ── Frame assembly ────────────────────────────────────────────────

def generate_frames():
    scenes = [
        (scene_title, 350),     # 8 frames x 350ms = 2.8s
        (scene_robot, 350),     # 4 frames x 350ms = 1.4s
        (scene_branding, 400),  # 4 frames x 400ms = 1.6s
    ]                           # total: 16 frames, ~5.8s loop

    all_frames = []
    all_durations = []
    for gen_fn, per_frame_ms in scenes:
        scene_frames = gen_fn()
        all_frames.extend(scene_frames)
        all_durations.extend([per_frame_ms] * len(scene_frames))
    return all_frames, all_durations


def make_animated_gif(frames, durations):
    quantized = [
        f.convert("RGB").quantize(colors=48).convert("RGB") for f in frames
    ]
    buf = BytesIO()
    quantized[0].save(
        buf, format="GIF", save_all=True,
        append_images=quantized[1:], duration=durations, loop=0,
    )
    return buf.getvalue()


async def main():
    preview = "--preview" in sys.argv

    print("Generating To Err is AI...")
    frames, durations = generate_frames()

    gif_data = make_animated_gif(frames, durations)
    num_chunks = (len(gif_data) + CHUNK_SIZE - 1) // CHUNK_SIZE
    print(f"Animated GIF: {len(frames)} frames, {len(gif_data)} bytes, {num_chunks} chunks")

    if num_chunks > 255:
        print(f"ERROR: {num_chunks} chunks exceeds protocol limit.")
        return

    if preview:
        out = Path(__file__).parent / "to_err_is_ai_preview.gif"
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

    print("Done! To Err is AI is on display.")


asyncio.run(main())
