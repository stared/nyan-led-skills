"""AGNTCon + MCPCon North America 2026: Quesma booth scenes for the Nyan Gear LED backpack.

Nine slow scenes on one frame: maximize the economic value of agentic coding
through insights from session transcripts. The device takes at most 255 chunks
per upload, so the scenes are split into playlists.
Storyboards: scripts/agntcon_mcpcon_na/README.md

Usage:
  uv run scripts/agntcon_mcpcon_na.py --list        # list playlists and scenes
  uv run scripts/agntcon_mcpcon_na.py main          # send the playlist (or a single scene)
  uv run scripts/agntcon_mcpcon_na.py --preview     # save preview GIFs of all scenes
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

S = DISPLAY_SIZE  # 64
CHUNK_SIZE = 196
FINALIZE = make_cmd(0x000F, 0x3603, b"\x01\x00\x00")
PREVIEW_DIR = Path(__file__).parent / "agntcon_mcpcon_na"
PREVIEW_SCALE = 4

# ── Pacing (device honours GIF frame durations) ──────────────────
CARD = 5500  # a text card stays up this long
LONG = 7000  # dense cards and punchlines
STEP = 800  # one step of a slow animation
BLINK = 900  # cursor / arrow blink period inside a held card

# ── Extra glyphs (5x7) ───────────────────────────────────────────
FONT = {
    **PIXEL_FONT_5x7,
    "/": [0b00001, 0b00010, 0b00010, 0b00100, 0b01000, 0b01000, 0b10000],
    "$": [0b00100, 0b01111, 0b10100, 0b01110, 0b00101, 0b11110, 0b00100],
    "%": [0b11001, 0b11010, 0b00010, 0b00100, 0b01000, 0b01011, 0b10011],
    "{": [0b00110, 0b00100, 0b00100, 0b01000, 0b00100, 0b00100, 0b00110],
    "}": [0b01100, 0b00100, 0b00100, 0b00010, 0b00100, 0b00100, 0b01100],
    '"': [0b01010, 0b01010, 0b01010, 0b00000, 0b00000, 0b00000, 0b00000],
    "_": [0b00000, 0b00000, 0b00000, 0b00000, 0b00000, 0b00000, 0b11111],
}

# ── Palette ──────────────────────────────────────────────────────
BG = (8, 8, 16)
TERM_BG = (10, 10, 14)
HEADER_BG = (28, 30, 48)
WHITE = (235, 235, 235)
AMBER = (255, 176, 0)
GREEN = (80, 220, 120)
TERM_GREEN = (90, 200, 110)
RED = (230, 60, 60)
CYAN = (90, 200, 255)
GREY = (110, 110, 130)
DIM = (50, 50, 64)
CLAUDE = (218, 119, 87)
GOLD = (255, 205, 60)
VERMILION = (230, 100, 70)
WALL = (55, 55, 72)
PAC = (255, 220, 0)

# ── Sprites ──────────────────────────────────────────────────────
ROBOT = [
    "...A...",
    ".CCCCC.",
    "CCWCWCC",
    "CCCCCCC",
    ".CRRRC.",
    ".C...C.",
]
ROBOT_COLORS = {"A": AMBER, "C": CYAN, "W": WHITE, "R": VERMILION}
MINI_ROBOT = [".C.", "CWC", "C.C"]

TOP_HAT = [
    ".HHHHH.",
    ".HHHHH.",
    ".BBBBB.",
    "HHHHHHH",
]
TOP_HAT_COLORS = {"H": (150, 150, 170), "B": VERMILION}

SPINNER_PLUS = ["...O...", "...O...", "...O...", "OOOOOOO", "...O...", "...O...", "...O..."]
SPINNER_X = ["O.....O", ".O...O.", "..O.O..", "...O...", "..O.O..", ".O...O.", "O.....O"]

FILE = [
    "WWWWW..",
    "W...WW.",
    "W.LL.WW",
    "W.....W",
    "W.LLL.W",
    "W.....W",
    "W.LL..W",
    "W.....W",
    "WWWWWWW",
]
FILE_COLORS = {"W": WHITE, "L": GREY}

PADLOCK_OPEN = [
    ".GGG.....",
    "G...G....",
    "G...G....",
    "....GGGGG",
    "....GGKGG",
    "....GGKGG",
    "....GGGGG",
]
PADLOCK_SHUT = [
    "..GGG..",
    ".G...G.",
    ".G...G.",
    "GGGGGGG",
    "GGGKGGG",
    "GGGKGGG",
    "GGGGGGG",
]
PADLOCK_COLORS = {"G": GOLD, "K": (90, 60, 0)}

TROPHY = [
    "GGGGGGG",
    "GGGGGGG",
    ".GGGGG.",
    "..GGG..",
    "...G...",
    "..GGG..",
]
TROPHY_COLORS = {"G": GOLD}

TICK = [
    "......G",
    ".....GG",
    "G...GG.",
    "GG.GG..",
    ".GGG...",
    "..G....",
]
TICK_COLORS = {"G": GREEN}


# ── Drawing helpers ───────────────────────────────────────────────

def new(bg=BG):
    return Image.new("RGB", (S, S), bg)


def put(img, x, y, color):
    if 0 <= x < S and 0 <= y < S:
        img.putpixel((x, y), color)


def rect(img, x0, y0, x1, y1, color, fill=False):
    for y in range(y0, y1 + 1):
        for x in range(x0, x1 + 1):
            if fill or y in (y0, y1) or x in (x0, x1):
                put(img, x, y, color)


def line(img, x0, y0, x1, y1, color):
    n = max(abs(x1 - x0), abs(y1 - y0), 1)
    for i in range(n + 1):
        put(img, round(x0 + (x1 - x0) * i / n), round(y0 + (y1 - y0) * i / n), color)


def draw_glyph(img, ch, x, y, color, scale=1):
    glyph = FONT.get(ch)
    if glyph is None:
        raise ValueError(f"no glyph for {ch!r}")
    for row in range(7):
        for col in range(5):
            if glyph[row] & (1 << (4 - col)):
                for dy in range(scale):
                    for dx in range(scale):
                        put(img, x + col * scale + dx, y + row * scale + dy, color)


def text_width(text, scale=1):
    return len(text) * 5 * scale + max(0, len(text) - 1) * scale


def text(img, s, x, y, color, scale=1):
    """Draw text left-aligned at (x, y); x=None centers it. Fails loudly on overflow."""
    w = text_width(s, scale)
    if x is None:
        x = (S - w) // 2
    if x < 0 or x + w > S:
        raise ValueError(f"text {s!r} overflows 64px at x={x} (width {w})")
    for ch in s:
        if ch != " ":
            draw_glyph(img, ch, x, y, color, scale)
        x += 6 * scale
    return x  # x just past the last char + spacing


def draw_art(img, art, palette, x, y):
    """Draw pixel art with its top-left at (x, y)."""
    for r, row in enumerate(art):
        for c, ch in enumerate(row):
            color = palette.get(ch)
            if color:
                put(img, x + c, y + r, color)


def draw_art_scaled(img, art, palette, x, y, scale):
    for r, row in enumerate(art):
        for c, ch in enumerate(row):
            color = palette.get(ch)
            if color:
                rect(img, x + c * scale, y + r * scale,
                     x + c * scale + scale - 1, y + r * scale + scale - 1, color, fill=True)


def hold(draw, total, period=None, bg=BG):
    """A card held for `total` ms. draw(img, f) gets f=0/1; with a period it alternates (blink)."""
    if period is None:
        img = new(bg)
        draw(img, 0)
        return [(img, total)]
    pair = []
    for f in range(2):
        img = new(bg)
        draw(img, f)
        pair.append(img)
    n = max(2, round(total / period))
    return [(pair[i % 2], total // n) for i in range(n)]


def header(label):
    def draw(img, f):
        rect(img, 0, 0, S - 1, 8, HEADER_BG, fill=True)
        text(img, label, 2, 1, AMBER)
    return draw


def card(lines, ms=CARD, hdr=None, deco=None, period=None, bg=BG, y0=None, gap=3):
    """Text card: lines are (text, color[, scale]) centered top-down; None adds a half gap.
    deco(img, f) draws visuals on top."""
    def draw(img, f):
        if hdr:
            hdr(img, f)
        y = y0 if y0 is not None else (12 if hdr else 4)
        for ln in lines:
            if ln is None:
                y += 6
                continue
            s, color, scale = (tuple(ln) + (1,))[:3]
            text(img, s, None, y, color, scale)
            y += 7 * scale + gap
        if deco:
            deco(img, f)
    return hold(draw, ms, period, bg)


def outro(lines, hdr=None, bg=BG):
    """Closing card: centered (text, color) lines, vertically centered; the last line blinks."""
    top = 9 if hdr else 0
    y0 = top + (S - top - (10 * len(lines) - 3)) // 2

    def draw(img, f):
        if hdr:
            hdr(img, f)
        for i, (s, color) in enumerate(lines):
            if i == len(lines) - 1 and f:
                continue
            text(img, s, None, y0 + 10 * i, color)
    return hold(draw, CARD, BLINK, bg)


def hbar(img, y, frac, color, h=4):
    rect(img, 2, y, 61, y + h + 1, GREY)
    if frac > 0:
        rect(img, 3, y + 1, 3 + max(0, round(57 * frac) - 1), y + h, color, fill=True)


def strike(img, s, y, color=RED):
    w = text_width(s)
    x = (S - w) // 2
    line(img, x - 1, y + 3, x + w, y + 3, color)


# ── 1. value: tokens in, value out (the frame) ───────────────────

def token_value_bars(img, tokens, value, top=4):
    text(img, "TOKENS", 2, top, AMBER)
    hbar(img, top + 10, tokens, AMBER)
    text(img, "ECONOMIC", 2, top + 22, GREEN)
    hbar(img, top + 32, value, GREEN)


def magnifier(img, cx, cy):
    for a in range(0, 360, 12):
        put(img, round(cx + 5 * math.cos(math.radians(a))), round(cy + 5 * math.sin(math.radians(a))), AMBER)
    line(img, cx + 4, cy + 4, cx + 8, cy + 8, AMBER)
    line(img, cx + 5, cy + 4, cx + 9, cy + 8, AMBER)


def scene_value():
    out = card([("AGENTIC", WHITE), ("CODING:", WHITE), None, ("TOKENS IN,", AMBER), ("ECONOMIC", GREEN),
                ("VALUE OUT.", GREEN)], y0=5)

    growth = [(0.1, 0.05), (0.25, 0.12), (0.4, 0.2), (0.55, 0.26), (0.7, 0.3), (0.85, 0.32), (1.0, 0.33)]
    for tokens, value in growth:
        out += hold(lambda img, f, t=tokens, v=value: token_value_bars(img, t, v), STEP)

    def stall(img, f):
        token_value_bars(img, 1.0, 0.33)
        if f == 0:
            text(img, "HMM.", None, 52, WHITE)
    out += hold(stall, CARD, BLINK)
    out += card([("WHERE DID", WHITE), ("THE TOKENS", AMBER), ("GO?", WHITE)], y0=16)

    log = ["$ ls", "$ cat", "$ ls", "$ cat", "$ grep", "$ ls", "$ cat", "$ ls", "$ cat", "$ ls"]
    for i in range(8):
        def scroll(img, f, i=i):
            for k in range(7):
                text(img, log[(i + k) % len(log)], 4, 2 + 9 * k, TERM_GREEN if k == 3 else GREY)
            magnifier(img, 14 + 5 * i, 32)
        out += hold(scroll, STEP, bg=TERM_BG)
    out += card([("THE ANSWER", WHITE), ("IS IN THE", WHITE), None, ("TRANSCRIPT", CYAN)], ms=LONG, y0=14)

    for value in (0.45, 0.6, 0.75, 0.9):
        out += hold(lambda img, f, v=value: token_value_bars(img, 1.0, v, top=2), STEP)

    out += hold(lambda img, f: token_value_bars(img, 1.0, 1.0, top=2), 2 * STEP)
    out += card([("MAX", WHITE), ("ECONOMIC", GREEN), ("VALUE", GREEN), ("PER TOKEN.", AMBER)], ms=LONG, y0=13)
    out += outro([("HOW? ASK", WHITE), ("THE HUMAN", WHITE), ("AT THIS", WHITE), ("BOOTH.", AMBER)])

    w = text_width("QUESMA")
    x0 = (S - w) // 2
    for k in range(1, 6):
        def sweep(img, f, k=k):
            text(img, "QUESMA", None, 26, WHITE)
            rect(img, x0, 36, x0 + round(w * k / 5) - 1, 37, GREEN, fill=True)
        out += hold(sweep, 400 if k < 5 else CARD)
    return out


# ── 2. confused: confused agents eat more tokens ─────────────────

def pacman(img, cx, cy, open_mouth, color=PAC, r=5):
    for y in range(-r, r + 1):
        for x in range(-r, r + 1):
            if x * x + y * y > r * r + 2:
                continue
            if open_mouth and x > 0 and abs(y) <= x * 0.8:
                continue
            put(img, cx + x, cy + y, color)
    put(img, cx, cy - 3, BG)  # eye


def scene_confused():
    hdr = header("CONFUSED?")
    counts = ["3K", "8K", "12K", "20K", "31K", "48K", "60K", "85K", "110K", "140K", "165K", "190K"]
    out = []
    for i, count in enumerate(counts):
        def eat(img, f, i=i, count=count):
            hdr(img, f)
            ax = 4 + (i % 6) * 11
            for dx in range(4, 64, 6):
                if dx > ax:
                    rect(img, dx, 33, dx + 1, 34, WHITE, fill=True)
            pacman(img, ax, 34, i % 2 == 0)
            text(img, "?", ax - 2, 20 + (i % 2), AMBER)
            text(img, "TOKENS", 2, 52, GREY)
            text(img, count, S - 2 - text_width(count), 52, AMBER)
        out += hold(eat, STEP)

    for i, n in enumerate([1, 42, 117, 230, 301, 339]):
        def log(img, f, i=i, n=n):
            hdr(img, f)
            text(img, "AGENT LOG:", 2, 11, AMBER)
            shift = 4 if i % 2 else 0  # half-line scroll so the log visibly moves
            for k in range(5):
                y = 21 + 8 * k - shift
                if 21 <= y <= 45:
                    text(img, "$ SAME CMD", 2, y, WHITE if y >= 41 else GREY)
            text(img, "RUN", 2, 55, GREY)
            label = f"#{n}"
            text(img, label, S - 2 - text_width(label), 55, AMBER)
        out += hold(log, CARD if n == 339 else STEP)

    def result(img, f):
        hdr(img, f)
        text(img, "TASK:", 2, 13, WHITE)
        text(img, "PASSED.", 2, 23, GREEN)
        text(img, "COST:", 2, 37, WHITE)
        text(img, "ABOUT 9X.", 2, 47, AMBER)
    out += hold(result, LONG)

    def burp(img, f):
        pacman(img, 26, 56, f == 0)
        text(img, "?", 36 + 2 * f, 50 - 3 * f, AMBER)
    out += card([("CONFUSED", AMBER), ("AGENTS", WHITE), ("EAT MORE", WHITE), ("TOKENS.", PAC)],
                ms=CARD, hdr=hdr, deco=burp, period=BLINK, y0=11)
    out += card([("GREEN TEST", GREEN), ("WON'T SHOW", WHITE), ("IT. THE", WHITE), ("TRANSCRIPT", CYAN), ("WILL.", CYAN)],
                ms=LONG, hdr=hdr, y0=12)
    out += outro([("FEED IT", WHITE), ("CONTEXT,", CYAN), ("NOT CASH.", AMBER), ("ASK ME.", GREEN)], hdr=hdr)
    return out


# ── 3. attention: human attention costs more than tokens ─────────

def balance(img, tilt, coins, human):
    """Beam pivots at (32, 38); tilt > 0 drops the right pan."""
    ly, ry = 38 - tilt, 38 + tilt
    line(img, 10, ly, 54, ry, GREY)
    for x0 in range(25, 40):
        h = 7 - abs(x0 - 32)
        if h > 0:
            rect(img, x0, 39 + (7 - h) * 3, x0, 60, WALL, fill=True)
    rect(img, 22, 61, 42, 62, GREY, fill=True)
    for cx, ey in ((10, ly), (54, ry)):
        line(img, cx, ey, cx, ey + 4, GREY)
        rect(img, cx - 5, ey + 5, cx + 5, ey + 5, WHITE, fill=True)
    for k in range(coins):
        y = ly + 3 - 3 * k
        rect(img, 6, y, 14, y + 1, GOLD, fill=True)
    if human:
        py = ry + 4
        rect(img, 53, py - 9, 55, py - 7, CYAN, fill=True)  # head
        line(img, 54, py - 6, 54, py - 3, CYAN)
        line(img, 51, py - 5, 57, py - 5, CYAN)
        put(img, 53, py - 2, CYAN)
        put(img, 55, py - 2, CYAN)
        put(img, 53, py - 1, CYAN)
        put(img, 55, py - 1, CYAN)


PROCEED_OPTIONS = ["1. YES", "2. ALWAYS", "3. NO"]


def triangle(img, x, y, color):
    for c, h in enumerate([5, 3, 1]):
        for dy in range(h):
            put(img, x + c, y + (5 - h) // 2 + dy, color)


def scene_attention():
    def question(img, f):
        text(img, "WHAT COSTS", None, 6, WHITE)
        text(img, "MORE?", None, 16, AMBER)
        balance(img, 0, 0, False)
    out = hold(question, CARD)

    beats = [(0, 0, False), (-1, 1, False), (-2, 2, False), (-3, 3, False),
             (2, 3, True), (5, 3, True), (8, 3, True)]
    for i, (tilt, coins, human) in enumerate(beats):
        def weigh(img, f, tilt=tilt, coins=coins, human=human, last=i == len(beats) - 1):
            text(img, "1M TOKENS", None, 2, GOLD)
            if human:  # "1 INTERRUPT" is 11 chars: a 3 px space makes it fit
                x = (S - (5 + 3 + text_width("INTERRUPT"))) // 2
                text(img, "1", x, 11, CYAN)
                text(img, "INTERRUPT", x + 8, 11, CYAN)
            if last:
                text(img, "CLUNK!", None, 21, WHITE)
            balance(img, tilt, coins, human)
        out += hold(weigh, CARD if i == len(beats) - 1 else STEP)

    out += card([("TOKENS:", WHITE), ("CHEAP.", GREEN), None, ("YOUR", WHITE), ("ATTENTION:", WHITE), ("NOT.", RED)],
                ms=LONG, y0=5)

    for i, wait in enumerate(["0:01", "0:30", "1:30", "4:00"]):
        def prompt(img, f, wait=wait):
            rect(img, 0, 0, S - 1, S - 1, CLAUDE)
            text(img, "PROCEED?", 4, 4, WHITE)
            for k, opt in enumerate(PROCEED_OPTIONS):
                text(img, opt, 8, 15 + 9 * k, GREY)
            if f == 0:
                triangle(img, 3, 16, CLAUDE)
            text(img, "WAITING", None, 45, GREY)
            text(img, wait, None, 54, AMBER if wait != "4:00" else RED)
        out += hold(prompt, 2 * STEP if i < 3 else CARD, BLINK if i == 3 else None, TERM_BG)

    out += card([("EVERY", WHITE), ("PROCEED?", CLAUDE), ("IS A", WHITE), ("CONTEXT", AMBER), ("SWITCH.", AMBER)],
                y0=6)
    out += outro([("SPEND", WHITE), ("TOKENS,", GOLD), ("SAVE", WHITE), ("HUMANS.", CYAN), ("TALK TO ME", GREEN)])
    return out


# ── 4. happy: make your Claude Code, Cursor, Codex happy ─────────

FACE_X = (10, 32, 54)


def face(img, cx, cy, mood, color, wink=False):
    r = 8
    for a in range(0, 360, 6):
        put(img, round(cx + r * math.cos(math.radians(a))), round(cy + r * math.sin(math.radians(a))), color)
    rect(img, cx - 3, cy - 3, cx - 2, cy - 2, color, fill=True)
    if wink:
        rect(img, cx + 2, cy - 2, cx + 3, cy - 2, color, fill=True)
    else:
        rect(img, cx + 2, cy - 3, cx + 3, cy - 2, color, fill=True)
    if mood == "happy":
        pts = [(-3, 2), (-2, 3), (-1, 4), (0, 4), (1, 4), (2, 3), (3, 2)]
    else:
        pts = [(-3, 5), (-2, 4), (-1, 3), (0, 3), (1, 3), (2, 4), (3, 5)]
    for dx, dy in pts:
        put(img, cx + dx, cy + dy, color)


def scene_happy():
    out = card([("MAKE YOUR", WHITE), ("CLAUDE", CLAUDE), ("CODE,", CLAUDE), ("CURSOR,", WHITE), ("CODEX", CYAN),
                ("HAPPY.", GREEN)], y0=3)

    reasons = [("TOO LONG", "AGENTS.MD"), ("NO QUICK", "SHORTCUT"), ("SAME ERR", "TEN TIMES")]
    happy = [False, False, False]
    for i, (a, b) in enumerate(reasons):
        for phase in ("sad", "struck", "bounce", "settled"):
            def draw(img, f, i=i, a=a, b=b, phase=phase, before=tuple(happy)):
                text(img, a, None, 6, WHITE)
                text(img, b, None, 16, AMBER)
                if phase != "sad":
                    strike(img, a, 6)
                    strike(img, b, 16)
                for k, cx in enumerate(FACE_X):
                    is_happy = before[k] or (k == i and phase in ("bounce", "settled"))
                    dy = -3 if (k == i and phase == "bounce") else 0
                    color = GOLD if is_happy else (GREY if k == i else DIM)
                    face(img, cx, 46 + dy, "happy" if is_happy else "sad", color)
            ms = {"sad": CARD - 1500, "struck": 1200, "bounce": 500, "settled": 1200}[phase]
            out += hold(draw, ms)
        happy[i] = True

    def bounce(img, f):
        for k, cx in enumerate(FACE_X):
            face(img, cx, 48 - (2 if (k + f) % 2 else 0), "happy", GOLD)
    out += card([("HAPPY", GOLD), ("AGENTS", WHITE), ("SHIP MORE,", GREEN), ("BURN LESS.", AMBER)],
                deco=bounce, period=BLINK, y0=2, gap=2)
    out += card([("YOUR", WHITE), ("SESSIONS", CYAN), ("KNOW WHAT", WHITE), ("MAKES THEM", WHITE), ("SAD.", GREY)],
                ms=LONG, y0=7)

    def wink(img, f):
        for cx in FACE_X:
            face(img, cx, 48, "happy", GOLD, wink=f == 1)
    out += card([("HOW HAPPY", WHITE), ("IS YOURS?", GOLD), ("ASK ME.", GREEN)], deco=wink, period=BLINK, y0=4)
    return out


# ── 5. weekly: weekly insights to tune your setup ────────────────

def calendar(img, filled):
    for i, day in enumerate("MTWTF"):
        x0 = 2 + 12 * i
        text(img, day, x0 + 3, 3, AMBER if i < filled else GREY)
        rect(img, x0, 12, x0 + 10, 44, GREY)
        if i < filled:
            for k in range(14):
                dx = (k * 7 + i * 3) % 8
                dy = (k * 13 + i * 5) % 29
                put(img, x0 + 1 + dx, 14 + dy, CYAN)
                put(img, x0 + 2 + dx, 14 + dy, CYAN)


def chat(img, my, badge=False):
    """Slack-style channel: header with a channel name, one bot message whose top is at y=my."""
    rect(img, 0, 0, S - 1, 8, HEADER_BG, fill=True)
    text(img, "# insights", 2, 1, WHITE)
    if my < S:
        rect(img, 2, my, 8, my + 6, GREEN, fill=True)
        rect(img, 11, my, 30, my + 1, WHITE, fill=True)
        if badge:
            rect(img, 33, my - 1, 39, my + 7, RED, fill=True)
            text(img, "1", 34, my, WHITE)
        for k, w in enumerate((50, 38, 46)):
            if my + 10 + 5 * k < S:
                rect(img, 11, my + 10 + 5 * k, 11 + w - 1, my + 11 + 5 * k, GREY, fill=True)


def scene_weekly():
    out = []
    for filled in range(6):
        def week(img, f, filled=filled):
            calendar(img, filled)
            text(img, "SESSIONS", None, 52, GREY)
        out += hold(week, STEP if filled < 5 else 2000)

    for my in (60, 40, 24, 12):
        out += hold(lambda img, f, my=my: chat(img, my), STEP // 2)

    def posted(img, f):
        chat(img, 12, badge=f == 0)
        text(img, "MONDAY", None, 41, AMBER)
        text(img, "INSIGHTS:", None, 51, WHITE)
    out += hold(posted, CARD, BLINK)

    tips = [["CACHE BUST", "SUBAGENT", "RUNS 6M,", "CACHE: 5M."], ["USE", "ultracode", "AND /goal,", "DON'T WAIT"], ["SEAT AT", "0% USE"]]
    for n, tip in enumerate(tips, 1):
        hdr = header(f"TIP {n}/3")
        for fixed in (False, True):
            def draw(img, f, tip=tip, fixed=fixed, hdr=hdr):
                hdr(img, f)
                dense = len(tip) > 3  # 4 lines: tighter spacing, tick moves down
                for k, s in enumerate(tip):
                    text(img, s, None, (13 + 9 * k) if dense else (14 + 10 * k), WHITE if k == 0 else AMBER)
                if fixed:
                    ty = 53 if dense else 50
                    draw_art(img, TICK, TICK_COLORS, 14, ty)
                    text(img, "FIXED.", 24, ty, GREEN)
            out += hold(draw, CARD if not fixed else 2000)

    out += card([("GET WEEKLY", WHITE), ("INSIGHTS", CYAN), ("TO TUNE", WHITE), ("YOUR SETUP", GREEN)], ms=LONG, y0=12)
    out += outro([("NEXT", WHITE), ("MONDAY:", AMBER), ("YOURS?", WHITE), ("ASK ME.", GREEN)])
    return out


# ── 6. sophisticated: be the most sophisticated ──────────────────

def stairs(img):
    for i in range(4):
        x0, top = 16 + 12 * i, 58 - 8 * i
        rect(img, x0, top, x0 + 11, 63, WALL, fill=True)
        rect(img, x0, top, x0 + 11, top, GREY, fill=True)


def robot_on(img, step, dy=0, hat=0, monocle=False):
    """Robot on stair `step` (0-3); hat: 0 none, else rows dropped in (1-3), or 4 resting."""
    x, top = 16 + 12 * step + 2, 58 - 8 * step
    y = top - 6 + dy
    draw_art(img, ROBOT, ROBOT_COLORS, x, y)
    if hat:
        draw_art(img, TOP_HAT, TOP_HAT_COLORS, x, y - 4 - (4 - hat) * 3)
    if monocle:
        for px, py in ((x + 3, y + 1), (x + 5, y + 1), (x + 3, y + 3), (x + 5, y + 3)):
            put(img, px, py, GOLD)


def scene_sophisticated():
    levels = [("LVL 1:", ["CHAT"]), ("LVL 2:", ["AGENT"]), ("LVL 3:", ["SUBAGENTS"]),
              ("LVL 4:", ["REFLECTS", "ON ITS", "SESSIONS"])]
    out = []
    for i, (lvl, lines) in enumerate(levels):
        if i:
            def jump(img, f, i=i):
                stairs(img)
                robot_on(img, i - 1, dy=-5)
            out += hold(jump, STEP // 2)
        frames = [(0, False, 3000)] if i < 3 else [(1, False, 400), (2, False, 400), (3, False, 400),
                                                   (4, False, 800), (4, True, 4000)]
        for hat, monocle, ms in frames:
            def draw(img, f, i=i, lvl=lvl, lines=lines, hat=hat, monocle=monocle):
                stairs(img)
                text(img, lvl, 2, 2, AMBER)
                for k, s in enumerate(lines):
                    text(img, s, 2, 11 + 9 * k, CYAN if i == 3 else WHITE)
                robot_on(img, i, hat=hat, monocle=monocle)
                if i >= 2:
                    for k in (1, 2):
                        step = max(0, i - k)
                        draw_art(img, MINI_ROBOT, {"C": CYAN, "W": WHITE},
                                 16 + 12 * step + 3 + 4 * k, 58 - 8 * step - 3)
            out += hold(draw, ms)

    out += card([("BE THE", WHITE), ("MOST", WHITE), ("SOPHISTI-", GOLD), ("CATED", GOLD), ("TEAM.", WHITE)], y0=8)

    def tip(img, f):
        draw_art_scaled(img, ROBOT, ROBOT_COLORS, 25, 46, 2)
        draw_art_scaled(img, TOP_HAT, TOP_HAT_COLORS, 25, 38 - 4 * f, 2)
    out += card([("LEVEL UP?", GOLD), ("TALK TO", WHITE), ("ME.", GREEN)], deco=tip, period=BLINK, y0=3)
    return out


# ── 7. open-source: the collector ────────────────────────────────

SPECKS = [(1, 1), (5, 3), (2, 5), (4, 7)]


def laptop(img):
    rect(img, 2, 36, 22, 50, GREY)
    rect(img, 0, 51, 24, 53, GREY, fill=True)


def bucket(img):
    line(img, 44, 44, 62, 44, CYAN)
    line(img, 44, 44, 47, 60, CYAN)
    line(img, 62, 44, 59, 60, CYAN)
    line(img, 47, 60, 59, 60, CYAN)
    line(img, 45, 48, 61, 48, (40, 90, 120))


def collector(img, fx, fy, specks=0, fall=0, lock=None):
    laptop(img)
    bucket(img)
    draw_art(img, FILE, FILE_COLORS, fx, fy)
    for k, (sx, sy) in enumerate(SPECKS):
        if k < specks:
            put(img, fx + sx, fy + sy + fall, RED)
    if lock:
        draw_art(img, lock, PADLOCK_COLORS, fx + 3, fy + 4)


def scene_open_source():
    out = card([("OPEN", WHITE), ("SOURCE", WHITE), ("COLLECTOR.", CYAN), None, ("APACHE 2.0", GREEN)], y0=8)
    fx, fy = 9, 39

    def read(img, f):
        text(img, "READS", None, 2, WHITE)
        text(img, "SESSION", None, 11, WHITE)
        text(img, "FILES.", None, 20, CYAN)
        collector(img, fx, fy - 2 * f, specks=4)
    out += hold(read, CARD, BLINK)

    for fall in (0, 4, 9, 14):
        def scrub(img, f, fall=fall):
            text(img, "SCRUBS", None, 2, WHITE)
            text(img, "SECRETS", None, 11, RED)
            text(img, "ON THE", None, 20, WHITE)
            text(img, "LAPTOP.", None, 29, WHITE)
            laptop(img)
            bucket(img)
            draw_art(img, FILE, FILE_COLORS, fx, fy)
            if fall < 14:
                for sx, sy in SPECKS:
                    put(img, fx + sx + fall // 3, fy + sy + fall, RED)
        out += hold(scrub, STEP if fall < 14 else CARD - 1500)

    for lock, ms in ((PADLOCK_OPEN, STEP), (PADLOCK_SHUT, CARD)):
        def encrypt(img, f, lock=lock):
            text(img, "ENCRYPTED", None, 2, GOLD)
            text(img, "WITH YOUR", None, 11, WHITE)
            text(img, "KEY.", None, 20, WHITE)
            collector(img, fx, fy, lock=lock)
        out += hold(encrypt, ms)

    for x, y in ((16, 32), (26, 26), (36, 28), (45, 34), (49, 42)):
        def fly(img, f, x=x, y=y):
            collector(img, x, y, lock=PADLOCK_SHUT)
        out += hold(fly, STEP // 2)

    def stored(img, f):
        text(img, "YOUR", None, 2, WHITE)
        text(img, "BUCKET.", None, 11, CYAN)
        text(img, "YOUR KEYS.", None, 20, GOLD)
        laptop(img)
        bucket(img)
        draw_art(img, FILE, FILE_COLORS, 49, 49)
        draw_art(img, PADLOCK_SHUT, PADLOCK_COLORS, 52, 53)
    out += hold(stored, CARD)

    out += card([("NO PROXY.", GREEN), None, ("NO HOOKS.", GREEN)], y0=20)
    out += card([("CLAUDE", CLAUDE), ("CODE,", CLAUDE), ("CODEX,", CYAN), ("CURSOR,", WHITE), ("COPILOT.", WHITE)],
                y0=8)
    out += outro([("READ THE", WHITE), ("CODE. ALL", WHITE), ("OF IT.", CYAN), ("THEN ASK", WHITE), ("ME.", GREEN)])
    return out


# ── 8. training: we made training data for top 3 labs ───────────

PODIUM = [(1, 22, 41, 38), (2, 3, 21, 45), (3, 42, 60, 51)]  # place, x0, x1, top


def podium(img, trophies):
    for place, x0, x1, top in PODIUM:
        rect(img, x0, top, x1, 63, WALL, fill=True)
        rect(img, x0, top, x1, top, GREY, fill=True)
        text(img, str(place), (x0 + x1) // 2 - 2, top + 4, GREY)
    for place, x0, x1, top, dy in trophies:
        draw_art(img, TROPHY, TROPHY_COLORS, (x0 + x1) // 2 - 3, top - 6 - dy)


def scene_training():
    # One trophy hops across the podium: one of the top 3, never saying which.
    out = []
    spots = {place: (x0, x1, top) for place, x0, x1, top in PODIUM}
    for place in (3, 2, 1, 3, 2, 1):
        for dy in (8, 0):
            def hop(img, f, cur=(place, *spots[place], dy)):
                text(img, "TOP 3", None, 6, GOLD, scale=2)
                podium(img, [cur])
            out += hold(hop, STEP // 2)

    def which(img, f):
        text(img, "TOP 3", None, 6, GOLD, scale=2)
        podium(img, [])
        if f == 0:
            for x0, x1, top in spots.values():
                text(img, "?", (x0 + x1) // 2 - 2, top - 9, GOLD)
    out += hold(which, CARD - 2000, BLINK)

    out += card([("WE MADE", WHITE), ("TRAINING", GOLD), ("DATA FOR", WHITE), ("A TOP 3", GOLD), ("LAB.", WHITE)],
                ms=LONG, y0=7)
    out += card([("SO WE KNOW", WHITE), ("WHAT A", WHITE), ("GOOD", GOLD), ("SESSION", CYAN), ("LOOKS LIKE", WHITE)],
                ms=LONG, y0=7)

    widths = [40, 28, 52, 20, 44, 34]
    for gold in range(len(widths) + 1):
        def transcript(img, f, gold=gold):
            for k, w in enumerate(widths):
                y = 6 + 9 * k
                text(img, "$", 2, y, GREY)
                rect(img, 9, y + 2, 9 + w, y + 4, GOLD if k < gold else DIM, fill=True)
        out += hold(transcript, STEP if gold < len(widths) else 2500, bg=TERM_BG)

    out += card([("YOURS ARE", WHITE), ("WORTH", WHITE), ("KEEPING.", GOLD)], y0=18)
    out += outro([("WHAT IS", WHITE), ("GOOD?", GOLD), ("ASK ME.", GREEN)])
    return out


# ── 9. mcp-call: talk to me as an MCP tool call ──────────────────

def scene_mcp_call():
    hdr = header("MCPCON")
    request = [('{"method":', GREY), ('"tools/', CYAN), ('call"', CYAN), ('"name":', GREY), ('"talk_to_', AMBER),
               ('human"}', AMBER)]
    out = []
    for n in range(1, len(request) + 1):
        def typed(img, f, n=n):
            hdr(img, f)
            for k, (s, color) in enumerate(request[:n]):
                text(img, s, 2, 11 + 9 * k, color)
        out += hold(typed, 2 * STEP if n < len(request) else CARD)

    def spin(img, f):
        hdr(img, f)
        draw_art(img, SPINNER_X if f else SPINNER_PLUS, {"O": CLAUDE}, 28, 28)
    out += hold(spin, 4 * STEP, STEP)

    def result(img, f):
        hdr(img, f)
        text(img, '{"result":', 2, 20, GREY)
        if f == 0:
            text(img, '"YES!"}', 14, 32, GREEN)
    out += hold(result, CARD, BLINK)
    out += outro([("NO AUTH.", WHITE), ("NO RATE", WHITE), ("LIMIT.", WHITE), ("JUST SAY", GREEN), ("HI.", GREEN)])
    return out


# ── Scene and playlist registry ──────────────────────────────────

SCENES = {
    "value": scene_value,
    "confused": scene_confused,
    "attention": scene_attention,
    "happy": scene_happy,
    "weekly": scene_weekly,
    "sophisticated": scene_sophisticated,
    "open-source": scene_open_source,
    "training": scene_training,
    "mcp-call": scene_mcp_call,
}

PLAYLISTS = {
    "main": ("booth loop", ["value", "confused", "attention", "happy", "weekly", "open-source"]),
    "extra": ("second loop", ["sophisticated", "training", "mcp-call"]),
}


def make_animated_gif(frames, durations, scale=1):
    quantized = [f.convert("RGB").quantize(colors=32).convert("RGB") for f in frames]
    if scale > 1:
        quantized = [f.resize((S * scale, S * scale), Image.NEAREST) for f in quantized]
    buf = BytesIO()
    quantized[0].save(
        buf, format="GIF", save_all=True,
        append_images=quantized[1:], duration=durations, loop=0,
    )
    return buf.getvalue()


def render(names):
    beats = [beat for name in names for beat in SCENES[name]()]
    return [img for img, _ in beats], [ms for _, ms in beats]


def build(names):
    frames, durations = render(names)
    gif = make_animated_gif(frames, durations)
    chunks = (len(gif) + CHUNK_SIZE - 1) // CHUNK_SIZE
    return frames, durations, gif, chunks


def resolve(arg):
    if arg in PLAYLISTS:
        return PLAYLISTS[arg][1]
    if arg in SCENES:
        return [arg]
    sys.exit(f"Unknown {arg!r}. Playlists: {', '.join(PLAYLISTS)}. Scenes: {', '.join(SCENES)}")


async def send(gif_data, num_chunks, label):
    print("Scanning for backpack...")
    device = await BleakScanner.find_device_by_filter(
        lambda d, adv: (adv.local_name or "").startswith(DEVICE_NAME_PREFIX),
        timeout=10,
    )
    if not device:
        sys.exit("Backpack not found!")
    print(f"Found: {device.name}")

    async with BleakClient(device) as client:
        await client.start_notify(NOTIFY_UUID, notification_handler)
        await send_wait(client, READY)
        errors = 0
        for idx in range(num_chunks):
            chunk = gif_data[idx * CHUNK_SIZE : (idx + 1) * CHUNK_SIZE]
            status = await send_wait(client, build_image_chunk(idx, chunk, num_chunks))
            if status != 0:
                errors += 1
                print(f"  chunk {idx}/{num_chunks} -> ERR status={status}")
            await asyncio.sleep(0.3)
        await send_wait(client, FINALIZE)
        await client.stop_notify(NOTIFY_UUID)

    if errors:
        sys.exit(f"FAILED: {errors}/{num_chunks} chunks errored; {label} may not display.")
    print(f"Done! {label} is on display.")


async def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]

    if "--list" in sys.argv:
        for name, (when, scenes) in PLAYLISTS.items():
            _, durations, _, chunks = build(scenes)
            print(f"{name:<7} {sum(durations) / 1000:5.0f}s {chunks:3} chunks  {when}")
            print(f"        {', '.join(scenes)}")
        return

    if "--preview" in sys.argv:
        PREVIEW_DIR.mkdir(exist_ok=True)
        for name in SCENES:
            frames, durations, gif, chunks = build([name])
            out = PREVIEW_DIR / f"{name}.gif"
            out.write_bytes(make_animated_gif(frames, durations, scale=PREVIEW_SCALE))
            print(f"{name}: {len(frames)} frames, {sum(durations) / 1000:.1f}s loop, {chunks} chunks")
        return

    if len(args) != 1:
        sys.exit("Pass one playlist or scene name (see --list), or --preview.")
    names = resolve(args[0])
    frames, durations, gif, chunks = build(names)
    print(f"{args[0]}: {len(names)} scene(s), {sum(durations) / 1000:.0f}s loop, "
          f"{len(gif)} bytes, {chunks} chunks")
    if chunks > 255:
        sys.exit(f"ERROR: {chunks} chunks exceeds protocol limit.")
    await send(gif, chunks, args[0])


asyncio.run(main())
