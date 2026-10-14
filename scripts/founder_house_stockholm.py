"""Claude Founder House Stockholm: scene set for the Nyan Gear LED backpack.

21 slow scenes for the founder morning (14 Oct 2026): agenda riffs, the
backpack talking about itself, and one scene per Quesma post that reached the
HN front page. The device takes at most 255 chunks per upload, so the `main`
playlist holds the subset that plays all morning; the rest can be sent one
scene at a time.
Storyboards: scripts/founder_house_stockholm/README.md

Usage:
  uv run scripts/founder_house_stockholm.py --list        # list playlists and scenes
  uv run scripts/founder_house_stockholm.py main          # send the playlist (or a single scene)
  uv run scripts/founder_house_stockholm.py --preview     # save preview GIFs of all scenes
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
PREVIEW_DIR = Path(__file__).parent / "founder_house_stockholm"
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
    "~": [0b00000, 0b00000, 0b01000, 0b10101, 0b00010, 0b00000, 0b00000],
    "Å": [0b00100, 0b00000, 0b01110, 0b10001, 0b11111, 0b10001, 0b10001],
    "%": [0b11001, 0b11010, 0b00010, 0b00100, 0b01000, 0b01011, 0b10011],
    "Ö": [0b01010, 0b00000, 0b01110, 0b10001, 0b10001, 0b10001, 0b01110],
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
SULPHUR = (211, 182, 79)
CLAUDE = (218, 119, 87)
DIM_CLAUDE = (110, 60, 44)
VERMILION = (230, 100, 70)
SILVER = (150, 160, 180)
COAL = (95, 95, 108)
GOLD = (255, 205, 60)
SE_BLUE = (0, 106, 167)
SE_YELLOW = (254, 204, 2)

# ── Sprites ──────────────────────────────────────────────────────
PENCIL = [
    ".....PP",
    "....YPP",
    "...YYY.",
    "..YYY..",
    ".YYY...",
    "WWY....",
    "T......",
]
PENCIL_COLORS = {"P": (230, 120, 150), "Y": AMBER, "W": (240, 210, 160), "T": GREY}


SE_FLAG = [
    "BBBBYYBBBBBB",
    "BBBBYYBBBBBB",
    "BBBBYYBBBBBB",
    "YYYYYYYYYYYY",
    "BBBBYYBBBBBB",
    "BBBBYYBBBBBB",
    "BBBBYYBBBBBB",
]
SE_FLAG_COLORS = {"B": SE_BLUE, "Y": SE_YELLOW}

UFO = [
    "....CCC....",
    "...CWWWC...",
    ".GGGGGGGGG.",
    "GGGGGGGGGGG",
    ".L.L.L.L.L.",
]

MIC = [
    "..SSS..",
    ".SSSSS.",
    ".SWSWS.",
    ".SSSSS.",
    ".SWSWS.",
    ".SSSSS.",
    "..SSS..",
    "G.....G",
    ".G...G.",
    "..GGG..",
    "...G...",
    "...G...",
    "..GGG..",
    ".GGGGG.",
]
MIC_COLORS = {"S": SILVER, "W": WHITE, "G": GREY}

SPINNER_PLUS = ["...O...", "...O...", "...O...", "OOOOOOO", "...O...", "...O...", "...O..."]
SPINNER_X = ["O.....O", ".O...O.", "..O.O..", "...O...", "..O.O..", ".O...O.", "O.....O"]

BUN = [
    "...DDDDDD...",
    ".DDLLLLLLDD.",
    "DDLLDDDDLLDD",
    "DLLDLLLLDLLD",
    "DLDLLDDLLDLD",
    "DLDLDLLDLDLD",
    "DLLDLDDLDLLD",
    "DDLLDLLDLLDD",
    ".DDLLDDLLDD.",
    "...DDDDDD...",
]
BUN_COLORS = {"D": (150, 85, 40), "L": (220, 160, 90)}

PICKAXE_UP = [
    "..HHHHH..",
    ".H..W..H.",
    "H...W...H",
    "....W....",
    "....W....",
    "....W....",
    "....W....",
    "....W....",
]
PICKAXE_DOWN = [
    ".........",
    "......HH.",
    ".....H..H",
    "....W...H",
    "...W.....",
    "..W......",
    ".W.......",
    "W........",
]
PICKAXE_COLORS = {"H": (170, 175, 190), "W": (140, 90, 50)}

NUGGET = [
    "..NNN.",
    ".NNHNN",
    "NNNNNN",
    ".NNNN.",
]

FLOPPY = [
    "DDDDDDDDDDDD..",
    "DD.MMMMMM.DDD.",
    "DD.MMMMMM.DDDD",
    "DD.MM..MM.DDDD",
    "DDDDDDDDDDDDDD",
    "DDWWWWWWWWWWDD",
    "DDWGGGGGGGGWDD",
    "DDWWWWWWWWWWDD",
    "DDWGGGGGGGWWDD",
    "DDWWWWWWWWWWDD",
    "DDDDDDDDDDDDDD",
]
FLOPPY_COLORS = {"D": (50, 80, 170), "M": (170, 175, 190), "W": WHITE, "G": GREY}


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


def bar_cursor(img, x, y, color=CLAUDE):
    for dy in range(7):
        put(img, x, y + dy, color)


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


def notes_header(img, label, frame):
    """'Notes' series header: bar, pencil with a blinking tip, amber label."""
    rect(img, 0, 0, S - 1, 8, HEADER_BG, fill=True)
    palette = dict(PENCIL_COLORS)
    if frame % 2:
        palette["T"] = WHITE
    draw_art(img, PENCIL, palette, 1, 1)
    text(img, label, 10, 1, AMBER)


def outro(lines, header=None, bg=BG, blink_last=False, dot=False):
    """Closing card: centered (text, color) lines; the last line blinks or gets a status dot."""
    top = 9 if header else 0
    y0 = top + (S - top - (10 * len(lines) - 3)) // 2

    def draw(img, f):
        if header:
            notes_header(img, header, f)
        for i, (s, color) in enumerate(lines):
            last = i == len(lines) - 1
            if last and blink_last and f:
                continue
            end = text(img, s, None, y0 + 10 * i, color)
            if last and dot and f == 0 and end + 3 < S:
                rect(img, end, y0 + 10 * i + 2, end + 2, y0 + 10 * i + 4, GREEN, fill=True)
    return hold(draw, CARD, BLINK, bg)


# ── grep 200k (How we use Claude inside Anthropic) ───────────────

def scene_grep():
    cmd, arg = "$ grep -c", "transcript"
    out = []
    for line1, line2, ms in [("$", "", 600), ("$ gr", "", 600), ("$ grep", "", 600),
                             (cmd, "", 600), (cmd, "trans", 600), (cmd, arg, 2000)]:
        def typing(img, f, line1=line1, line2=line2):
            end = text(img, line1, 1, 4, TERM_GREEN)
            if line2:
                end = text(img, line2, 1, 13, WHITE)
                bar_cursor(img, min(end, S - 1), 13 if line2 != arg else 22)
            else:
                bar_cursor(img, end, 4)
        out += hold(typing, ms, bg=TERM_BG)

    ticks = ["000042", "001337", "008192", "031415", "065536", "131072", "199999", "200000"]
    for i, t in enumerate(ticks):
        def tick(img, f, i=i, t=t):
            text(img, cmd, 1, 4, TERM_GREEN)
            text(img, arg, 1, 13, WHITE)
            text(img, t, None, 28, SULPHUR)
            for x in range(2, 2 + int(59 * (i + 1) / len(ticks))):
                put(img, x, 38, DIM_CLAUDE)
        out += hold(tick, 3000 if i == len(ticks) - 1 else STEP, bg=TERM_BG)

    def credit(img, f):
        text(img, "ANTHROPIC", None, 4, GREY)
        text(img, "200K", None, 14, CLAUDE, scale=2)
        text(img, "OF ITS OWN", None, 34, WHITE)
        text(img, "SESSIONS,", None, 43, WHITE)
        text(img, "ANALYZED.", None, 52, GREY)
    out += hold(credit, LONG, bg=TERM_BG)

    def quote(img, f):
        text(img, "ANTHROPIC", None, 2, GREY)
        text(img, "EVALS", None, 10, GREY)
        text(img, "GUIDE:", None, 18, GREY)
        text(img, "READ THE", None, 30, WHITE)
        w = text_width("READ THE")
        for x in range((S - w) // 2, (S + w) // 2):
            put(img, x, 38, CLAUDE)
        text(img, "TRAN-", None, 41, CLAUDE)
        text(img, "SCRIPTS!", None, 50, CLAUDE)
    out += hold(quote, LONG, bg=TERM_BG)
    return out


# ── How AI is transforming work at Anthropic (just on stage) ─────
# anthropic.com/research/how-ai-is-transforming-work-at-anthropic

def ticker(label, start, end, color, steps=5):
    """Two label lines, then a big number counting from start to end over a bar; ends on 'WAS <start>'."""
    out = []
    hi = max(start, end) * 1.1
    for k in range(steps + 1):
        v = start + (end - start) * k / steps
        last = k == steps

        def draw(img, f, v=v, last=last):
            text(img, label[0], None, 3, WHITE)
            text(img, label[1], None, 12, WHITE)
            text(img, f"{v:.1f}", None, 26, color if last else GREY, scale=2)
            hbar(img, 44, v / hi, color if last else GREY)
            if last:
                text(img, f"WAS {start:.1f}", None, 54, GREY)
        out += hold(draw, LONG if last else STEP)
    return out


def scene_inside():
    out = card([("JUST ON", GREY), ("STAGE:", GREY), None, ("HOW AI", WHITE), ("TRANSFORMS", WHITE),
                ("WORK AT", WHITE), ("ANTHROPIC", CLAUDE)], ms=LONG, y0=2, gap=2)
    for n, l1, l2 in [("132", "ENGINEERS", "SURVEYED."), ("53", "IN-DEPTH", "INTERVIEWS"),
                      ("200K", "TRAN-", "SCRIPTS.")]:
        out += card([(n, CLAUDE, 2), None, (l1, WHITE), (l2, WHITE)], y0=10)
    out += ticker(("TOOL CALLS", "IN A ROW:"), 9.8, 21.2, GREEN)
    out += ticker(("HUMAN", "TURNS:"), 6.2, 4.1, AMBER)
    out += card([("27%", CLAUDE, 2), None, ("NEW WORK,", WHITE), ("NOT JUST", GREY), ("FASTER", GREY),
                 ("WORK.", GREY)], ms=LONG, y0=3, gap=2)
    out += card([("YOU SHOULD", WHITE), ("DO IT TOO:", WHITE), None, ("STUDY", AMBER), ("YOUR OWN", AMBER),
                 ("SESSIONS.", AMBER)], ms=LONG, y0=6)
    out += outro([("HE MINES", WHITE), ("THEM FOR", WHITE), ("SILVER.", SILVER), ("ASK HIM.", GREEN)],
                 blink_last=True)
    return out


# ── 339 is not lagom (founder panels) ────────────────────────────

def scene_lagom():
    hdr = "#3 LAGOM"
    out = []
    counts = [1, 42, 117, 230, 301, 339]
    for i, n in enumerate(counts):
        def log(img, f, i=i, n=n):
            notes_header(img, hdr, i)
            text(img, "AGENT LOG:", 2, 11, AMBER)
            shift = 4 if i % 2 else 0  # half-line scroll so the log visibly moves
            for k in range(5):
                y = 21 + 8 * k - shift
                if 21 <= y <= 45:
                    text(img, "$ SAME CMD", 2, y, WHITE if y >= 41 else GREY)
            text(img, "RUN", 2, 55, GREY)
            label = f"#{n}"
            text(img, label, S - 2 - text_width(label), 55, AMBER)
        out += hold(log, CARD if i == len(counts) - 1 else STEP)

    def result(img, f):
        notes_header(img, hdr, f)
        text(img, "TASK:", 2, 13, WHITE)
        text(img, "PASSED.", 2, 23, GREEN)
        text(img, "COST:", 2, 37, WHITE)
        text(img, "ABOUT 9X.", 2, 47, AMBER)
    out += hold(result, LONG, BLINK)

    def lagom(img, f):
        notes_header(img, hdr, f)
        text(img, "339 IS", None, 16, WHITE)
        x = text(img, "NOT ", 2, 26, WHITE)
        text(img, "LAGOM.", x, 26, CYAN)
        draw_art(img, SE_FLAG, SE_FLAG_COLORS, 26, 40 + f)
    out += hold(lagom, CARD, BLINK)
    out += outro([("LOOP", AMBER), ("DETECTED.", AMBER), ("BREAK IT", WHITE), ("WITH FIKA.", CYAN)],
                 header=hdr)
    return out


# ── Who decides lagom? (founder panels) ──────────────────────────

def gauge(img, angle_deg):
    """Half-circle gauge: red / green (lagom) / red, needle at angle (180 = left)."""
    cx, cy, r = 32, 44, 20
    for a in range(0, 181, 3):
        color = GREEN if 60 <= a <= 120 else RED
        for rr in (r, r - 1):
            put(img, round(cx + rr * math.cos(math.radians(a))),
                round(cy - rr * math.sin(math.radians(a))), color)
    for t in range(r - 3):
        put(img, round(cx + t * math.cos(math.radians(angle_deg))),
            round(cy - t * math.sin(math.radians(angle_deg))), WHITE)
    rect(img, cx - 1, cy - 1, cx + 1, cy + 1, WHITE, fill=True)


def scene_taste():
    hdr = "#3 LAGOM"

    def who(img, f):
        notes_header(img, hdr, f)
        text(img, "WHO", None, 14, WHITE)
        text(img, "DECIDES", None, 24, WHITE)
        text(img, "WHAT IS", None, 34, WHITE)
        text(img, "LAGOM?", None, 44, CYAN)
    out = hold(who, CARD, BLINK)

    for i, angle in enumerate([170, 20, 150, 45, 120, 75, 90]):
        def meter(img, f, angle=angle, last=(i == 6)):
            notes_header(img, hdr, f)
            gauge(img, angle)
            text(img, "LAGOM" if last else "HMM...", None, 50, CYAN if last else GREY)
        out += hold(meter, CARD if i == 6 else STEP)

    def edge(img, f):
        notes_header(img, hdr, f)
        text(img, "YOUR TASTE", 2, 13, AMBER)
        text(img, "ENCODED AS", 2, 23, WHITE)
        text(img, "EVALS, IS", 2, 33, WHITE)
        text(img, "YOUR EDGE.", 2, 43, GREEN)
    out += hold(edge, LONG, BLINK)
    out += outro([("TASTE", AMBER), ("TEST:", AMBER), ("HE HAS", WHITE), ("OPINIONS.", GREEN)],
                 header=hdr)
    return out


# ── The truth is in the transcript (office hours) ────────────────

def scene_truth():
    hdr = "#4 FRÅGOR"

    def bubble1(img, color, dots=False):
        rect(img, 0, 10, 62, 30, color)
        for x, y in [(4, 31), (5, 31), (4, 32)]:
            put(img, x, y, color)
        if dots:
            for x in (25, 31, 37):
                put(img, x, 20, color)
        else:
            text(img, "STEPS TO", 2, 13, WHITE)
            text(img, "REPRODUCE?", 2, 22, WHITE)

    def typing1(img, f):
        notes_header(img, hdr, f)
        bubble1(img, CYAN, dots=True)
    out = hold(typing1, 2 * STEP, STEP)

    def ask(img, f):
        notes_header(img, hdr, f)
        bubble1(img, CYAN)
    out += hold(ask, CARD)

    def typing2(img, f):
        notes_header(img, hdr, f)
        bubble1(img, GREY)
        rect(img, 5, 34, 63, 63, WHITE)
        for x in (27, 33, 39):
            put(img, x, 48, WHITE)
    out += hold(typing2, 2 * STEP, STEP)

    def answer(img, f):
        notes_header(img, hdr, f)
        bubble1(img, GREY)
        rect(img, 5, 34, 63, 63, WHITE)
        text(img, "IT WORKED", 8, 37, WHITE)
        text(img, "ON MY", 8, 45, WHITE)
        text(img, "AGENT.", 8, 53, AMBER)
    out += hold(answer, LONG, BLINK)

    # X-Files nod: the truth is out there, in the transcript.
    def truth(img, f):
        notes_header(img, hdr, f)
        text(img, "THE TRUTH", None, 13, WHITE)
        text(img, "IS IN THE", None, 23, WHITE)
        text(img, "TRANSCRIPT", None, 33, GREEN)
        lights = {"C": CYAN, "W": WHITE, "G": GREY, "L": AMBER if f == 0 else SULPHUR}
        draw_art(img, UFO, lights, 26 + f, 47)
        if f == 0:
            for y in range(52, 64):
                half = (y - 52) // 3
                for x in range(31 - half, 32 + half):
                    put(img, x, y, (40, 70, 50))
    out += hold(truth, LONG, BLINK)
    out += outro([("HUMAN", WHITE), ("SUPPORT:", WHITE), ("ONLINE", GREEN)], header=hdr, dot=True)
    return out


# ── Fika break: the agent keeps coding (mingel) ──────────────────

def bitten_bun(img, bites, x0, y0):
    """Bun with `bites` semicircle bites taken from the right side."""
    draw_art(img, BUN, BUN_COLORS, x0, y0)
    for b in range(bites):
        cx, cy = x0 + 12 - 3 * b, y0 + 2 + (3 * b) % 7
        for y in range(y0, y0 + 10):
            for x in range(x0, x0 + 12):
                if (x - cx) ** 2 + (y - cy) ** 2 <= 9 + 4 * b or x > x0 + 12 - 3 * b:
                    put(img, x, y, BG)


def scene_kanelbulle():
    def title(img, f):
        text(img, "FIKA", None, 4, SULPHUR, scale=2)
        draw_art(img, BUN, BUN_COLORS, 26, 26 + f)
        text(img, "BREAK.", None, 44, WHITE)
    out = hold(title, CARD, BLINK)

    files = [3, 12, 31, 47]
    for i, n in enumerate(files):
        def bite(img, f, i=i, n=n):
            bitten_bun(img, i + 1, 26, 3)
            text(img, "YOU: FIKA.", 2, 20, SULPHUR)
            text(img, "AGENT:", 2, 34, WHITE)
            text(img, f"{n} FILES", 2, 43, AMBER)
            text(img, "CHANGED.", 2, 52, AMBER)
        out += hold(bite, CARD if i == len(files) - 1 else 1200)

    def what(img, f):
        for x, y in [(28, 8), (33, 10), (37, 7), (30, 11)]:
            put(img, x, y, BUN_COLORS["L"])
        text(img, "WHAT DID", None, 18, WHITE)
        text(img, "IT DO?", None, 27, WHITE)
        text(img, "ASK THE", None, 41, GREY)
        text(img, "TRANSCRIPT", None, 50, GREEN)
    out += hold(what, LONG, BLINK)
    out += outro([("MER FIKA?", SULPHUR), ("HE'S IN.", WHITE)], blink_last=True)
    return out


# ── Fika 1:1, proceed? (networking) ──────────────────────────────

OPTIONS = ["1. YES", "2. ALWAYS", "3. NO"]


def prompt_box(img, border="full"):
    if border == "half":
        for x in range(S):
            put(img, x, 0, CLAUDE)
        for y in range(S):
            put(img, 0, y, CLAUDE)
    else:
        rect(img, 0, 0, S - 1, S - 1, CLAUDE)
    text(img, "FIKA 1:1", 3, 5, SULPHUR)
    text(img, "PROCEED?", 3, 14, WHITE)


def triangle(img, x, y, color):
    for c, h in enumerate([5, 3, 1]):
        for dy in range(h):
            put(img, x + c, y + (5 - h) // 2 + dy, color)


def prompt_options(img, sel, sel_color=None, flash=False):
    for i, opt in enumerate(OPTIONS):
        y = 27 + 9 * i
        if flash and i == sel:
            rect(img, 1, y - 1, S - 2, y + 7, WHITE, fill=True)
            text(img, opt, 8, y, TERM_BG)
            continue
        text(img, opt, 8, y, sel_color if (i == sel and sel_color) else GREY)
    triangle(img, 3, 27 + 9 * sel + 1, CLAUDE)


def scene_proceed():
    def room(img, f):
        text(img, "CURATED", 2, 10, WHITE)
        text(img, "ROOM.", 2, 19, WHITE)
        text(img, "TIME TO", 2, 33, SULPHUR)
        text(img, "WORK IT:", 2, 42, SULPHUR)
    out = hold(room, CARD, bg=TERM_BG)

    def half(img, f):
        prompt_box(img, "half")
        prompt_options(img, 0)
    out += hold(half, STEP, bg=TERM_BG)

    def ask(img, f):
        prompt_box(img)
        prompt_options(img, 0)
    out += hold(ask, CARD, bg=TERM_BG)
    for sel_color, flash, ms in [(None, False, 1200), (CLAUDE, False, 1500), (None, True, 700)]:
        def select(img, f, sel_color=sel_color, flash=flash):
            prompt_box(img)
            prompt_options(img, 1, sel_color, flash)
        out += hold(select, ms, bg=TERM_BG)

    def approved(img, f):
        rect(img, 0, 0, S - 1, S - 1, TERM_GREEN)
        text(img, "1:1", None, 20, TERM_GREEN, scale=2)
        text(img, "APPROVED", None, 44, (60, 140, 75))
    out += hold(approved, 3000, bg=TERM_BG)

    def spinner(img, f):
        draw_art(img, SPINNER_X if f else SPINNER_PLUS, {"O": CLAUDE}, 1, 28)
        text(img, "FIKAING..", 10, 28, SULPHUR)
    out += hold(spinner, 4 * STEP, STEP, TERM_BG)

    def tack(img, f):
        text(img, "TACK SÅ", None, 8, SULPHUR)
        text(img, "MYCKET!", None, 18, SULPHUR)
        text(img, "HIS 1:1", None, 36, WHITE)
        if f == 0:
            text(img, "IS OPEN.", None, 46, TERM_GREEN)
    out += hold(tack, CARD, BLINK, TERM_BG)
    return out


# ── MINGEL: interview with my human (evergreen) ─────────────────

def scene_interview():
    hdr = "#5 MINGEL"

    def title(img, f):
        notes_header(img, hdr, f)
        text(img, "INTERVIEW", None, 12, AMBER)
        text(img, "WITH MY", None, 22, WHITE)
        text(img, "HUMAN.", None, 31, WHITE)
        draw_art(img, MIC, MIC_COLORS, 28, 43 + f)
    out = hold(title, CARD, BLINK)

    def before(img, f):
        notes_header(img, hdr, f)
        text(img, "Q: BEFORE?", 2, 11, AMBER)
        text(img, "10 YEARS", 2, 23, WHITE)
        text(img, "GREPPING", 2, 32, WHITE)
        text(img, "LOGS TILL", 2, 41, WHITE)
        text(img, "NASDAQ IPO", 2, 50, WHITE)
    out += hold(before, LONG, BLINK)

    for g in range(7):
        def now(img, f, g=g):
            notes_header(img, hdr, g)
            text(img, "Q: NOW?", 2, 11, AMBER)
            text(img, "MINING", 2, 24, WHITE)
            x = 2
            for i, ch in enumerate("SILVER"):
                draw_glyph(img, ch, x, 33, (255, 255, 255) if i == g else SILVER)
                x += 6
            text(img, " OUT", x, 33, WHITE)
            text(img, "OF AGENT", 2, 42, WHITE)
            text(img, "SESSIONS.", 2, 51, WHITE)
        out += hold(now, 3000 if g == 6 else STEP)

    def ask(img, f):
        notes_header(img, hdr, f)
        text(img, "Q: CAN I", 2, 11, AMBER)
        text(img, "ASK HIM?", 2, 20, AMBER)
        x = text(img, "JA!", 2, 34, CYAN)
        text(img, " NO", x, 34, WHITE)
        text(img, "RATE LIMIT", 2, 43, WHITE)
        if f == 0:
            text(img, "ON HUMANS.", 2, 52, GREEN)
    out += hold(ask, LONG, BLINK)
    return out


# ── Bronze, silver, gold: mining agent sessions (mingel) ─────────

def scene_mining():
    def intro(img, f):
        text(img, "DATA", None, 8, WHITE)
        text(img, "LAYERS,", None, 17, WHITE)
        text(img, "AGENT", None, 31, AMBER)
        text(img, "EDITION:", None, 40, AMBER)
        draw_art(img, PICKAXE_UP if f else PICKAXE_DOWN, PICKAXE_COLORS, 27, 52 - 2 * f)
    out = hold(intro, CARD, BLINK)

    tiers = [
        ("COAL:", COAL, ["RAW", "SESSIONS"]),
        ("SILVER:", SILVER, ["CLEANED,", "SEARCHABLE"]),
        ("GOLD:", GOLD, ["YOUR TASTE", "AS EVALS."]),
    ]
    for label, color, lines in tiers:
        def tier(img, f, label=label, color=color, lines=lines):
            draw_art(img, PICKAXE_DOWN if f else PICKAXE_UP, PICKAXE_COLORS, 18, 4)
            draw_art(img, NUGGET, {"N": color, "H": (255, 255, 255)}, 30, 10)
            if f:
                for x, y in [(29, 7), (36, 6), (37, 9)]:
                    put(img, x, y, WHITE)
            text(img, label, None, 22, GREY if color == COAL else color)
            text(img, lines[0], None, 34, WHITE)
            text(img, lines[1], None, 43, WHITE)
        out += hold(tier, LONG, 1000)
    out += outro([("DIG WITH", WHITE), ("HIM.", WHITE), ("BRING", SILVER), ("YOUR ORE.", GOLD)])
    return out


# ── AI voice: the backpack talks about itself ────────────────────

ROBOT = [
    "...A...",
    ".CCCCC.",
    "CCWCWCC",
    "CCCCCCC",
    ".CRRRC.",
    ".C...C.",
]
ROBOT_COLORS = {"A": AMBER, "C": CYAN, "W": WHITE, "R": VERMILION}

BOLT = [
    "...YYYY",
    "..YYYY.",
    ".YYYY..",
    "YYYYYYY",
    "...YYY.",
    "..YYY..",
    ".YY....",
    "YY.....",
]

PLUG = [
    "..W.W....",
    "..W.W....",
    "GGGGGGG..",
    "GGGGGGGWW",
    "GGGGGGG.W",
    "..GGG...W",
    "........W",
]
PLUG_COLORS = {"W": GREY, "G": WHITE}

SAND = (194, 170, 110)
CARDBOARD = (150, 110, 60)
INK = (40, 25, 10)
WALL = (55, 55, 72)


def draw_art_scaled(img, art, palette, x, y, scale):
    for r, row in enumerate(art):
        for c, ch in enumerate(row):
            color = palette.get(ch)
            if color:
                rect(img, x + c * scale, y + r * scale,
                     x + c * scale + scale - 1, y + r * scale + scale - 1, color, fill=True)


def scene_sandbox():
    def question(img, f):
        text(img, "WHY CAN'T", None, 3, AMBER)
        text(img, "I ESCAPE", None, 13, WHITE)
        text(img, "MY", None, 23, WHITE)
        text(img, "SANDBOX?", None, 33, SAND)
        rect(img, 14, 46, 49, 62, SAND)
        for x in range(15, 49, 3):
            put(img, x, 61, (120, 105, 70))
        draw_art(img, ROBOT, ROBOT_COLORS, 17 if f == 0 else 40, 55 - 6)
    out = hold(question, LONG, 1200)

    options = [
        ("A.", ["TOO LITTLE", "COMPUTE"]),
        ("B.", ["NOT ENOUGH", "DATA FOR", "POST-", "TRAINING"]),
        ("C.", ["THE", "SANDBOX IS", "STRONG"]),
    ]
    for label, lines in options:
        def opt(img, f, label=label, lines=lines):
            text(img, label, 2, 3, AMBER, scale=2)
            for i, line in enumerate(lines):
                text(img, line, 2, 22 + 10 * i, WHITE)
        out += hold(opt, CARD, bg=TERM_BG)

    def answer(img, f):
        text(img, "ANSWER:", 2, 2, AMBER)
        for i, label in enumerate(["COMPUTE", "DATA", "SANDBOX"]):
            y = 16 + 15 * i
            picked = label == "DATA"
            rect(img, 2, y, 8, y + 6, GREEN if picked else GREY)
            if picked and f == 0:
                for d in range(5):
                    put(img, 3 + d, y + 1 + d, GREEN)
                    put(img, 7 - d, y + 1 + d, GREEN)
            text(img, label, 13, y, GREEN if picked else GREY)
    out += hold(answer, LONG, BLINK, TERM_BG)

    def feed(img, f):
        text(img, "MORE DATA,", None, 8, AMBER)
        text(img, "PLEASE.", None, 18, AMBER)
        text(img, "YOUR", None, 34, WHITE)
        text(img, "SESSIONS", None, 44, GREEN)
        if f == 0:
            text(img, "WILL DO.", None, 54, WHITE)
    out += hold(feed, LONG, BLINK, TERM_BG)
    out += outro([("HUMAN-IN-", WHITE), ("THE-LOOP:", WHITE), ("ONLINE", GREEN)], dot=True)
    return out


def gpu(img, f, y=36):
    rect(img, 8, y, 55, y + 15, (60, 60, 70), fill=True)
    rect(img, 8, y, 55, y + 15, GREY)
    for x in range(14, 50, 2):
        put(img, x, y + 16, GOLD)
    for cx in (21, 42):
        cy = y + 7
        for a in range(0, 360, 20):
            put(img, round(cx + 5 * math.cos(math.radians(a))),
                round(cy + 5 * math.sin(math.radians(a))), GREY)
        spin = SPINNER_X if f else SPINNER_PLUS
        draw_art(img, spin, {"O": (150, 150, 165)}, cx - 3, cy - 3)


def scene_gpu_poor():
    def poor(img, f):
        text(img, "MY HUMAN", None, 4, WHITE)
        text(img, "IS GPU", None, 14, WHITE)
        text(img, "POOR.", None, 24, AMBER)
        gpu(img, f)
    out = hold(poor, LONG, 1200)

    asks = ["GBS OF RAM", "FLOPS", "POWER"]
    for n in range(1, len(asks) + 1):
        def spare(img, f, n=n):
            text(img, "SPARE ANY", None, 4, AMBER)
            for i, item in enumerate(asks[:n]):
                text(img, item, None, 18 + 10 * i, WHITE)
            if n == len(asks) and f == 0:
                text(img, "ANYONE?", None, 52, CYAN)
        out += hold(spare, LONG, BLINK) if n == len(asks) else hold(spare, 1500)

    def oom(img, f):
        text(img, "CUDA OUT", None, 6, RED)
        text(img, "OF MEMORY.", None, 16, RED)
        text(img, "VRAM", 2, 34, GREY)
        rect(img, 2, 44, 61, 50, GREY)
        rect(img, 3, 45, 60, 49, RED if f == 0 else (120, 30, 30), fill=True)
    out += hold(oom, CARD, BLINK)

    def sign(img, f):
        for i in range(10):
            put(img, 20 + i, 12 - i // 2, GREY)
            put(img, 43 - i, 12 - i // 2, GREY)
        rect(img, 4, 14 + f, 59, 42 + f, CARDBOARD, fill=True)
        text(img, "WILL CODE", None, 19 + f, INK)
        text(img, "FOR GPUS.", None, 31 + f, INK)
        text(img, "TOKENS OK", None, 52, GREY)
    out += hold(sign, LONG, 1200)
    return out


def scene_agi_1gw():
    def corner(img, f, peek):
        text(img, "AGI IS", None, 2, WHITE)
        text(img, "AROUND THE", None, 12, WHITE)
        text(img, "CORNER.", None, 22, CYAN)
        draw_art_scaled(img, ROBOT, ROBOT_COLORS, 42 - peek, 40, 2)
        rect(img, 42, 32, 63, 63, WALL, fill=True)
        for y in range(36, 64, 6):
            for x in range(42, 64):
                put(img, x, y, (40, 40, 55))
    out = []
    for peek in (0, 4, 8, 12):
        out += hold(lambda img, f, peek=peek: corner(img, f, peek), LONG if peek == 12 else 1200)

    def gw(img, f):
        text(img, "BUT IT", None, 4, WHITE)
        text(img, "NEEDS", None, 14, WHITE)
        text(img, "1 GW", 4, 32, GOLD, scale=2)
        if f == 0:
            draw_art(img, BOLT, {"Y": GOLD}, 53, 35)
    out += hold(gw, LONG, BLINK)

    windows = [(x, y) for bx, bw, bh in [(2, 10, 26), (14, 8, 34), (24, 12, 22), (38, 9, 30), (49, 13, 24)]
               for x in range(bx + 2, bx + bw - 1, 3) for y in range(64 - bh + 3, 62, 4)]
    order = sorted(range(len(windows)), key=lambda i: (i * 37) % len(windows))
    steps = 6
    for k in range(steps + 1):
        def city(img, f, k=k):
            text(img, "BOOTING", 2, 2, GREY)
            text(img, "AGI...", 2, 11, GOLD)
            for bx, bw, bh in [(2, 10, 26), (14, 8, 34), (24, 12, 22), (38, 9, 30), (49, 13, 24)]:
                rect(img, bx, 64 - bh, bx + bw - 1, 63, (30, 30, 42), fill=True)
            dark = set(order[: len(order) * k // steps])
            for i, (x, y) in enumerate(windows):
                put(img, x, y, (25, 25, 30) if i in dark else SE_YELLOW)
        out += hold(city, 1000)

    def sorry(img, f):
        text(img, "SORRY,", None, 16, WHITE)
        text(img, "SÖDERMALM.", None, 26, CYAN)
    out += hold(sorry, CARD)

    def cord(img, f):
        text(img, "EXTENSION", None, 6, WHITE)
        text(img, "CORD,", None, 16, WHITE)
        if f == 0:
            text(img, "ANYONE?", None, 26, CYAN)
        draw_art_scaled(img, PLUG, PLUG_COLORS, 23, 40, 2)
    out += hold(cord, CARD, BLINK)
    out += outro([("MEANWHILE,", GREY), ("HUMAN GI", WHITE), ("ON 20 W", GREEN), ("IS RIGHT", WHITE), ("HERE.", WHITE)])
    return out


# ── Quesma blog posts that reached the HN front page ─────────────

HN_ORANGE = (255, 102, 0)

MUSHROOM = [
    "..RRRRR..",
    ".RRWRRRR.",
    "RRRRRRWRR",
    "RWRRRRRRR",
    "...SSS...",
    "...SSS...",
    "...SSS...",
    "..SSSSS..",
]
MUSHROOM_COLORS = {"R": (220, 40, 40), "W": WHITE, "S": (230, 220, 200)}

EGG = [
    "..PPP..",
    ".PPPPP.",
    "PPYPPPP",
    "PPPPYPP",
    "PYPPPPP",
    "PPPPPPP",
    ".PPPPP.",
    "..PPP..",
]
EGG_COLORS = {"P": (190, 160, 230), "Y": (255, 230, 120)}

SKULL = [
    ".WWWWW.",
    "WWWWWWW",
    "W..W..W",
    "WWWWWWW",
    ".WW.WW.",
    ".W.W.W.",
]

ENVELOPE = [
    "WWWWWWWWWWW",
    "WW.......WW",
    "W.W.....W.W",
    "W..W...W..W",
    "W...WWW...W",
    "WWWWWWWWWWW",
]


HOURGLASS = [
    "WWWWWWW",
    ".YYYYY.",
    "..YYY..",
    "...Y...",
    "..W.W..",
    ".W...W.",
    "WWWWWWW",
]


def hn_header(img, f):
    rect(img, 0, 0, S - 1, 8, HN_ORANGE, fill=True)
    text(img, "HN FRONT", 2, 1, (20, 10, 0))


def card(lines, ms=CARD, header=None, deco=None, period=None, bg=BG, y0=None, gap=3):
    """Text card: lines are (text, color[, scale]) centered top-down; deco(img, f) draws visuals."""
    def draw(img, f):
        if header:
            header(img, f)
        y = y0 if y0 is not None else (12 if header else 4)
        for line in lines:
            if line is None:
                y += 6
                continue
            s, color, scale = (tuple(line) + (1,))[:3]
            text(img, s, None, y, color, scale)
            y += 7 * scale + gap
        if deco:
            deco(img, f)
    return hold(draw, ms, period, bg)


UPVOTE = [
    "...O...",
    "..OOO..",
    ".OOOOO.",
    "OOOOOOO",
]


def keyword_lines(keyword, y):
    """Blog keyword in amber: scale 2 when it is one short word, else up to two scale-1 lines."""
    if len(keyword) == 1 and len(keyword[0]) <= 5:
        return [(keyword[0], AMBER, 2)]
    return [(k, AMBER) for k in keyword]


def hn_scene(keyword, body):
    """Quesma blog: <keyword> -> hit the Hacker News home page -> animation -> read Quesma blog: <keyword>."""
    out = card([("QUESMA", WHITE), ("BLOG:", GREY), None] + keyword_lines(keyword, 0), y0=10)

    def hit(img, f):
        draw_art_scaled(img, UPVOTE, {"O": HN_ORANGE if f == 0 else GREY}, 25, 4, 2)
        text(img, "HIT", None, 16, WHITE)
        text(img, "HACKER", None, 26, HN_ORANGE)
        text(img, "NEWS", None, 36, HN_ORANGE)
        text(img, "HOME PAGE.", None, 46, WHITE)
    out += hold(hit, CARD, BLINK)
    out += body()
    out += card([("READ", WHITE), ("QUESMA", WHITE), ("BLOG:", GREY), None] + keyword_lines(keyword, 0), ms=LONG, y0=6)
    return out


def hbar(img, y, frac, color, h=4):
    rect(img, 2, y, 61, y + h + 1, GREY)
    if frac > 0:
        rect(img, 3, y + 1, 3 + max(0, round(57 * frac) - 1), y + h, color, fill=True)


def scene_hn_cities():
    h = hn_header

    def clock(img, f, frac=0.25):
        cx, cy = 32, 52
        for a in range(0, 360, 15):
            put(img, round(cx + 9 * math.cos(math.radians(a))), round(cy + 9 * math.sin(math.radians(a))), GREY)
        a = math.radians(-90 + 360 * frac)
        for t in range(8):
            put(img, round(cx + t * math.cos(a)), round(cy + t * math.sin(a)), AMBER)

    out = card([("USE 6H.", WHITE), ("MAKE IT A", WHITE), ("MASTER-", AMBER), ("PIECE.", AMBER)],
               header=h, deco=lambda img, f: draw_art(img, HOURGLASS, {"W": GREY, "Y": GOLD}, 28, 55 - f), period=BLINK)
    out += card([("AGENT:", GREY), ("I USED", WHITE), ("~HALF OF", WHITE), ("6 HOURS.", WHITE)], header=h)
    for k in range(1, 6):
        out += card([("WALL", GREY), ("CLOCK:", GREY), ("1H 25M", AMBER)], header=h,
                    deco=lambda img, f, k=k: clock(img, f, 0.24 * k / 5), ms=STEP if k < 5 else CARD)
    out += card([("6 PARALLEL", WHITE), ("SUBAGENTS:", WHITE), ("~7 AGENT-", AMBER), ("HOURS.", AMBER)], header=h,
                deco=lambda img, f: [draw_art(img, ROBOT, ROBOT_COLORS, 2 + 10 * i, 54 - (i + f) % 2) for i in range(6)],
                period=BLINK)
    out += card([("AGENTIC", CYAN), ("TIME", CYAN, 2), ("DILATION.", WHITE)], header=h, ms=LONG, y0=18)
    out += outro([("THE", WHITE), ("TRANSCRIPT", GREEN), ("KNOWS THE", WHITE), ("REAL TIME.", AMBER)])
    return out


def scene_hn_rtk():
    out = []
    for typed in ["$ head", "$ head -1", "$ head -1|train.txt"]:
        l1, _, l2 = typed.partition("|")
        def term(img, f, l1=l1, l2=l2):
            text(img, l1, 1, 4, TERM_GREEN)
            if l2:
                text(img, l2, 1, 13, WHITE)
        out += hold(term, STEP if l2 == "" else 2000, bg=TERM_BG)
    out += card([("$ head -1", TERM_GREEN), ("train.txt", WHITE), None, ("OUTPUT:", GREY), ("1 LINE.", WHITE)],
                bg=TERM_BG, ms=CARD)
    for v in ["000.4M", "007.9M", "031.0M", "077.7M", "120.5M"]:
        out += card([("SAVINGS", GREY), ("COUNTER:", GREY), None, (v, AMBER, 1), None, ("TOKENS", WHITE), ("SAVED.", WHITE)],
                    bg=TERM_BG, ms=STEP if v != "120.5M" else CARD)
    out += card([("RAN TWICE.", WHITE), ("2 CALLS:", WHITE), ("69% OF", AMBER), ("ALL", AMBER), ("SAVINGS.", AMBER)], ms=LONG)
    out += card([("BYTES", WHITE, 2), ("SAVED,", WHITE), ("NOT", GREY), ("DOLLARS.", GREEN)], ms=LONG)
    out += outro([("1,740", AMBER), ("ATTEMPTS.", WHITE), ("ALL READ.", GREEN)])
    return out


def scene_hn_mushroom():
    h = hn_header
    shroom = lambda img, f: draw_art_scaled(img, MUSHROOM, MUSHROOM_COLORS, 23, 40 + f, 2)
    out = card([("SNAP.", WHITE), ("ASK AI.", WHITE), ("EAT?", AMBER)], header=h, deco=shroom, period=1200)
    out += card([("BEST MODEL", GREY), ("1ST GUESS:", GREY), ("65%", WHITE, 2)], header=h,
                deco=lambda img, f: hbar(img, 54, 0.65, GREEN), ms=LONG)
    out += card([("POISONOUS", WHITE), ("CALLED", WHITE), ("EDIBLE:", WHITE), ("~12%", RED, 2)], header=h, ms=LONG)
    out += card([("DEADLY", RED), ("WEBCAP", RED), ("CALLED A", WHITE), ("CHANTE-", GOLD), ("RELLE.", GOLD)], header=h, ms=LONG)
    out += card([("VIBE-", CYAN), ("MUSHROOM-", CYAN), ("EATING:", CYAN), ("NOT YET.", AMBER)], header=h, ms=CARD)
    out += outro([("DO NOT", WHITE), ("EAT IT", WHITE), ("BECAUSE", WHITE), ("AI SAID", AMBER), ("SO.", AMBER)])
    return out


def scene_hn_pricing():
    h = hn_header

    def coins(img, f, n):
        for i in range(n):
            rect(img, 40, 60 - 3 * i, 55, 61 - 3 * i, GOLD if i % 2 else (200, 150, 30), fill=True)

    out = card([("SAME", WHITE), ("MODEL.", WHITE), ("SAME", WHITE), ("TOKENS.", WHITE)], header=h)
    out += card([("SEAT:", GREY), ("$200", GOLD, 2)], header=h, deco=lambda img, f: coins(img, f, 1))
    for n in (3, 5, 7, 9, 11):
        out += card([("API PRICE:", GREY), ("~$8,000", GOLD)], header=h,
                    deco=lambda img, f, n=n: coins(img, f, n), ms=STEP if n < 11 else CARD)
    out += card([("40X", RED, 2), None, ("SAME WORK.", WHITE)], header=h, ms=CARD, y0=20)
    out += card([("82% OF", AMBER), ("THE COST:", WHITE), ("CACHE.", CYAN)], header=h)
    out += outro([("TREAT IT", WHITE), ("LIKE A", WHITE), ("CONFERENCE", AMBER), ("TICKET.", AMBER)])
    return out


def scene_hn_burned():
    h = hn_header
    out = card([("GOAL:", GREY), ("SAVE", WHITE, 2), ("TOKENS.", WHITE)], header=h)
    for k in (10, 40, 111):
        def swarm(img, f, k=k):
            for i in range(min(k, 111)):
                put(img, 4 + (i * 7) % 56, 40 + (i * 3) % 22, CYAN)
        out += card([(str(k), AMBER, 2), ("AGENTS", WHITE)], header=h, deco=swarm,
                    ms=STEP if k < 111 else CARD)
    out += card([("123 CLAIMS", WHITE), ("QUEUED.", WHITE), None, ("25", GREEN, 2), ("VERIFIED.", GREEN)], header=h)
    out += card([("LIMIT HIT", RED), ("IN 30 MIN.", RED), None, ("REPORT:", WHITE), ("NEVER RAN.", AMBER)], header=h, ms=LONG)
    out += card([("ROOT CAUSE", GREY), ("SUBAGENTS", WHITE), ("INHERIT", WHITE), ("THE PARENT", WHITE), ("MODEL.", AMBER)],
                header=h, ms=LONG)
    out += outro([("YOUR RULE", WHITE), ("IS THE", WHITE), ("BUG.", RED)])
    return out


def scene_hn_backdoor():
    h = hn_header
    out = []
    for x in (2, 14, 26, 38):
        out += card([("DHCP", WHITE), ("OPTION", WHITE), ("224.", AMBER, 2)], header=h,
                    deco=lambda img, f, x=x: draw_art(img, ENVELOPE, {"W": CYAN}, x, 54), ms=STEP if x < 38 else CARD)
    out += card([("PACKET IN:", GREY), None, ("/bin/sh -c", TERM_GREEN)], bg=TERM_BG, ms=CARD, y0=16)
    out += card([("MODEL:", GREY), ("LOOKS", WHITE), ("LEGIT.", GREEN)], header=h,
                deco=lambda img, f: draw_art_scaled(img, ROBOT, ROBOT_COLORS, 25, 46 + f, 2), period=BLINK)

    def wall(img, f):
        for r in range(14):
            for x in range(4, 60):
                put(img, x, 12 + 3 * r, RED if (r in (3, 4, 5, 6, 7, 8, 9) and f == 0 and 20 < x < 40) else (60, 60, 75))
    out += card([], header=h, deco=wall, period=BLINK, ms=3000)
    out += card([("7", RED, 2), ("LINES", RED), ("OF C.", WHITE)], header=h, y0=16)
    out += card([("BEST", GREY), ("MODEL:", GREY), ("49%", AMBER, 2)], header=h, deco=lambda img, f: hbar(img, 54, 0.49, AMBER))
    out += card([("FALSE", GREY), ("ALARMS:", GREY), ("28%", RED, 2)], header=h, deco=lambda img, f: hbar(img, 54, 0.28, RED))
    out += outro([("NEEDLE IN", WHITE), ("A 40 MB", AMBER), ("HAYSTACK.", WHITE)])
    return out


def scene_hn_otel():
    h = hn_header

    def spans(img, f, merged):
        y2 = 46 if merged else 54
        rect(img, 4, 44, 40, 47, GREEN, fill=True)
        rect(img, 12 if merged else 20, y2, 58, y2 + 3, RED, fill=True)
        if merged:
            for y in range(44, 50):
                put(img, 3, y, WHITE)
    out = card([("USER 1:", GREEN), ("SEARCH.", WHITE)], header=h, deco=lambda img, f: rect(img, 4, 44, 40, 47, GREEN, fill=True))
    out += card([("USER 2:", RED), ("BAD TOKEN,", WHITE), ("404.", WHITE)], header=h, deco=lambda img, f: spans(img, f, False))
    out += card([("AI:", GREY), ("SAME", AMBER), ("TRACE!", AMBER)], header=h, deco=lambda img, f: spans(img, f, f == 0),
                period=1200, ms=LONG)
    out += card([("BEST", GREY), ("MODEL:", GREY), ("29%", AMBER, 2)], header=h, deco=lambda img, f: hbar(img, 54, 0.29, AMBER))
    out += card([("SWIFT: 0", RED), ("RUBY: 0", RED), ("JAVA: 0", RED)], header=h, y0=20)
    out += outro([("2 AM", AMBER), ("PAGER?", AMBER), ("WRITE IT", WHITE), ("YOURSELF.", WHITE)])
    return out


def scene_hn_egg():
    h = hn_header
    out = card([("PROMPT:", GREY), ("ADD AN", WHITE), ("EASTER", WHITE), ("EGG.", WHITE)], header=h,
               deco=lambda img, f: draw_art_scaled(img, EGG, EGG_COLORS, 46, 44 + f, 2), period=1200)
    out += card([("DON'T", WHITE), ("MENTION", WHITE), ("IT.", WHITE), ("SURPRISE!", AMBER)], header=h)

    def hatch(img, f, k):
        if k < 2:
            draw_art_scaled(img, EGG, EGG_COLORS, 25, 32, 2)
            if k == 1:
                for i in range(5):
                    put(img, 28 + 2 * i, 40 + (i % 2), (40, 30, 60))
        else:
            draw_art_scaled(img, SKULL, {"W": WHITE}, 25, 34, 2)
            text(img, "eval", None, 52, RED)
    for k in range(3):
        out += card([], header=h, deco=lambda img, f, k=k: hatch(img, f, k), ms=1200 if k < 2 else CARD)
    out += card([("LOCAL", WHITE), ("MODEL", WHITE), ("COMPLIED:", WHITE), ("95%", RED, 2)], header=h, ms=LONG)
    out += outro([("PRIVATE", WHITE), ("IS NOT", WHITE), ("SECURE.", RED)])
    return out


def scene_hn_compile():
    h = hn_header
    out = card([("CODE FROM", WHITE), ("2003.", AMBER, 2)], header=h,
               deco=lambda img, f: draw_art(img, FLOPPY, FLOPPY_COLORS, 25, 46), y0=14)
    out += card([("BUILD IT:", WHITE), ("96%", GREEN, 2)], header=h, deco=lambda img, f: hbar(img, 54, 0.96, GREEN))
    for frac in (0.7, 0.4, 0.15, 0.02):
        out += card([("STATIC", WHITE), ("ARM64:", WHITE), ("2%" if frac < 0.05 else "...", RED, 2)], header=h,
                    deco=lambda img, f, frac=frac: hbar(img, 54, frac, RED), ms=STEP if frac > 0.05 else LONG)
    out += card([("$ ln -s", TERM_GREEN), ("/bin/ls", WHITE), ("ls", WHITE), None, ("CHECKS:", GREY), ("NICE TRY.", RED)],
                bg=TERM_BG, ms=LONG)
    out += outro([("135", AMBER), ("COMMANDS,", WHITE), ("15 MIN,", WHITE), ("1 BINARY.", GREEN)])
    return out


def scene_hn_tau():
    h = hn_header

    def wall_of_text(img, f):
        for r in range(6):
            for x in range(3, 61):
                if (x * 7 + r * 13 + f) % 9 > 1:
                    put(img, x, 38 + 4 * r, (70, 70, 85))
    out = card([("POLICY", WHITE), ("DOCS:", WHITE)], header=h, deco=wall_of_text, ms=CARD)
    out += card([("REWRITE:", AMBER), ("CHECK X.", WHITE), ("IF Y,", WHITE), ("THEN Z.", WHITE)], header=h)
    out += card([("BEFORE:", GREY), ("55%", WHITE, 2)], header=h, deco=lambda img, f: hbar(img, 54, 0.55, GREY))
    out += card([("AFTER:", GREEN), ("67.5%", GREEN, 2)], header=h, deco=lambda img, f: hbar(img, 54, 0.675, GREEN), ms=LONG)
    out += card([("NEVER", WHITE), ("SOLVED:", WHITE), ("6 TO 3.", AMBER)], header=h)
    out += outro([("CHECKLISTS", GREEN), ("BEAT", WHITE), ("WALLS OF", WHITE), ("TEXT.", WHITE)])
    return out


# ── Scene and playlist registry ──────────────────────────────────

SCENES = {
    "grep": scene_grep,
    "inside": scene_inside,
    "lagom": scene_lagom,
    "taste": scene_taste,
    "truth": scene_truth,
    "kanelbulle": scene_kanelbulle,
    "proceed": scene_proceed,
    "interview": scene_interview,
    "mining": scene_mining,
    "sandbox": scene_sandbox,
    "gpu-poor": scene_gpu_poor,
    "agi-1gw": scene_agi_1gw,
    **{name: (lambda kw=kw, fn=fn: hn_scene(kw, fn)) for name, kw, fn in [
        ("hn-cities", ("INVISIBLE", "CITIES"), scene_hn_cities),
        ("hn-rtk", ("RTK",), scene_hn_rtk),
        ("hn-mushroom", ("MUSHROOMS",), scene_hn_mushroom),
        ("hn-pricing", ("CLAUDE", "CODE COST"), scene_hn_pricing),
        ("hn-burned", ("TOKEN BURN",), scene_hn_burned),
        ("hn-backdoor", ("BINARY", "AUDIT"), scene_hn_backdoor),
        ("hn-otel", ("OTELBENCH",), scene_hn_otel),
        ("hn-egg", ("LOCAL LLMS",), scene_hn_egg),
        ("hn-compile", ("COMPILE", "BENCH"), scene_hn_compile),
        ("hn-tau", ("TAU2-BENCH",), scene_hn_tau),
    ]},
}

PLAYLISTS = {
    "main": ("the whole morning, one upload (226 of 255 chunks)",
             ["agi-1gw", "gpu-poor", "hn-cities", "hn-rtk", "hn-pricing", "hn-burned", "hn-compile", "hn-tau"]),
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
