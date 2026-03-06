"""Send boring white text to the backpack. No fun allowed."""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from PIL import Image
from display import (
    DISPLAY_SIZE,
    PIXEL_FONT_5x7,
    display_image,
    _wrap_words,
    _pixel_text_width,
)

S = DISPLAY_SIZE

def make_boring_text(text: str) -> Image.Image:
    img = Image.new("RGB", (S, S), (0, 0, 0))
    char_w, char_h, spacing, line_gap = 5, 7, 1, 3
    lines = _wrap_words(text, S, char_w, spacing)
    total_h = len(lines) * char_h + (len(lines) - 1) * line_gap
    y_start = (S - total_h) // 2
    white = (255, 255, 255)

    for line_num, line in enumerate(lines):
        line_w = _pixel_text_width(line, char_w, spacing)
        cx = (S - line_w) // 2
        y = y_start + line_num * (char_h + line_gap)
        for ch in line:
            glyph = PIXEL_FONT_5x7.get(ch)
            if glyph is None or ch == " ":
                cx += char_w + spacing
                continue
            for row in range(char_h):
                for col in range(char_w):
                    if glyph[row] & (1 << (4 - col)):
                        px, py = cx + col, y + row
                        if 0 <= px < S and 0 <= py < S:
                            img.putpixel((px, py), white)
            cx += char_w + spacing
    return img

asyncio.run(display_image(make_boring_text("AI Tinkerers Warsaw")))
