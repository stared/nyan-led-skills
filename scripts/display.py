"""Display a custom image on the Nyan Gear backpack.

Usage:
  uv run scripts/display.py                    # Show test pattern
  uv run scripts/display.py image.png          # Show an image file
  uv run scripts/display.py image.gif          # Show a GIF
  uv run scripts/display.py --color red        # Show solid color
  uv run scripts/display.py --color "#00ff00"  # Show hex color
  uv run scripts/display.py --text "HI"        # Show text
  uv run scripts/display.py --test-resolution  # Test 32/48/64 to find display size
"""

import asyncio
import sys
from io import BytesIO
from pathlib import Path

from bleak import BleakClient, BleakScanner
from PIL import Image, ImageDraw, ImageFont

DEVICE_NAME_PREFIX = "YS"
WRITE_UUID = "0000fff2-0000-1000-8000-00805f9b34fb"
NOTIFY_UUID = "0000fff1-0000-1000-8000-00805f9b34fb"

# Display is 64x64 (confirmed via --test-resolution)
DISPLAY_SIZE = 64

# Protocol constants (reverse-engineered from ATOTOZONE-family protocol)
CONST_SEQ = bytes.fromhex("c1020901010c01000d01000e0100140301090a11040001000a1207")
CONST2 = bytes.fromhex("c4000013")
PAYLOAD_LEN_MARKER = bytes.fromhex("81c4")

# ACK tracking
ack_event = asyncio.Event()
last_status = -1


def notification_handler(sender, data: bytearray):
    global last_status
    ack_event.set()
    if len(data) >= 11 and data[0] == 0xAA and data[1] == 0x55:
        echo = (data[5] << 8) | data[6]
        last_status = data[10]
        st = "OK" if last_status == 0 else f"ERR=0x{last_status:02x}"
        print(f"  ← echo=0x{echo:04x} {st}")


def make_packet(data: bytes) -> bytes:
    """Build aa55ffff packet with checksum."""
    pkt_len = len(data) + 1
    raw = bytes([0xAA, 0x55, 0xFF, 0xFF, pkt_len]) + data
    total = sum(raw)
    return raw + bytes([total & 0xFF, (total >> 8) & 0xFF])


def make_cmd(cmd_id: int, sub_cmd: int, args: bytes = b"") -> bytes:
    data = cmd_id.to_bytes(2, "big") + b"\x00\xc1\x02" + sub_cmd.to_bytes(2, "big") + args
    return make_packet(data)


def build_image_chunk(chunk_idx: int, gif_chunk: bytes, total_chunks: int) -> bytes:
    """Build image data chunk in the protocol format."""
    # Index format: 00 <idx> 00
    idx_bytes = bytes([0x00, chunk_idx, 0x00])
    # Pad payload to 196 bytes
    padded = gif_chunk + b"\x00" * max(0, 196 - len(gif_chunk))
    payload = (
        idx_bytes
        + CONST_SEQ
        + bytes([total_chunks])  # frame_count = total number of chunks
        + idx_bytes
        + CONST2
        + PAYLOAD_LEN_MARKER
        + padded[:196]
    )
    return make_packet(payload)


READY = make_cmd(0x0009, 0x0802, b"\x00\x00")
FINALIZE = make_cmd(0x000f, 0x3603, b"\x01\x00\x00")


async def send_wait(client: BleakClient, data: bytes, timeout: float = 5.0) -> int:
    """Send packet and wait for ACK. Returns status code."""
    global last_status
    ack_event.clear()
    last_status = -1
    await client.write_gatt_char(WRITE_UUID, data, response=False)
    try:
        await asyncio.wait_for(ack_event.wait(), timeout=timeout)
    except asyncio.TimeoutError:
        pass
    return last_status


def image_to_gif(img: Image.Image) -> bytes:
    """Convert image to GIF bytes, resized to display size."""
    img = img.convert("RGB").resize((DISPLAY_SIZE, DISPLAY_SIZE), Image.LANCZOS)
    buf = BytesIO()
    img.save(buf, format="GIF")
    return buf.getvalue()


def make_test_pattern() -> Image.Image:
    """Rainbow gradient test pattern."""
    img = Image.new("RGB", (DISPLAY_SIZE, DISPLAY_SIZE))
    for y in range(DISPLAY_SIZE):
        for x in range(DISPLAY_SIZE):
            r = int(255 * x / DISPLAY_SIZE)
            g = int(255 * y / DISPLAY_SIZE)
            b = int(255 * (DISPLAY_SIZE - x) / DISPLAY_SIZE)
            img.putpixel((x, y), (r, g, b))
    return img


def make_solid_color(color_str: str) -> Image.Image:
    """Create solid color image."""
    if color_str.startswith("#"):
        r = int(color_str[1:3], 16)
        g = int(color_str[3:5], 16)
        b = int(color_str[5:7], 16)
        color = (r, g, b)
    else:
        color_map = {
            "red": (255, 0, 0), "green": (0, 255, 0), "blue": (0, 0, 255),
            "white": (255, 255, 255), "yellow": (255, 255, 0),
            "cyan": (0, 255, 255), "magenta": (255, 0, 255),
            "orange": (255, 128, 0), "purple": (128, 0, 255),
        }
        color = color_map.get(color_str.lower(), (255, 255, 255))
    return Image.new("RGB", (DISPLAY_SIZE, DISPLAY_SIZE), color)


PIXEL_FONT_5x7: dict[str, list[int]] = {
    "A": [0b01110, 0b10001, 0b10001, 0b11111, 0b10001, 0b10001, 0b10001],
    "B": [0b11110, 0b10001, 0b10001, 0b11110, 0b10001, 0b10001, 0b11110],
    "C": [0b01110, 0b10001, 0b10000, 0b10000, 0b10000, 0b10001, 0b01110],
    "D": [0b11110, 0b10001, 0b10001, 0b10001, 0b10001, 0b10001, 0b11110],
    "E": [0b11111, 0b10000, 0b10000, 0b11110, 0b10000, 0b10000, 0b11111],
    "F": [0b11111, 0b10000, 0b10000, 0b11110, 0b10000, 0b10000, 0b10000],
    "G": [0b01110, 0b10001, 0b10000, 0b10111, 0b10001, 0b10001, 0b01110],
    "H": [0b10001, 0b10001, 0b10001, 0b11111, 0b10001, 0b10001, 0b10001],
    "I": [0b01110, 0b00100, 0b00100, 0b00100, 0b00100, 0b00100, 0b01110],
    "J": [0b00111, 0b00010, 0b00010, 0b00010, 0b00010, 0b10010, 0b01100],
    "K": [0b10001, 0b10010, 0b10100, 0b11000, 0b10100, 0b10010, 0b10001],
    "L": [0b10000, 0b10000, 0b10000, 0b10000, 0b10000, 0b10000, 0b11111],
    "M": [0b10001, 0b11011, 0b10101, 0b10101, 0b10001, 0b10001, 0b10001],
    "N": [0b10001, 0b11001, 0b10101, 0b10011, 0b10001, 0b10001, 0b10001],
    "O": [0b01110, 0b10001, 0b10001, 0b10001, 0b10001, 0b10001, 0b01110],
    "P": [0b11110, 0b10001, 0b10001, 0b11110, 0b10000, 0b10000, 0b10000],
    "Q": [0b01110, 0b10001, 0b10001, 0b10001, 0b10101, 0b10010, 0b01101],
    "R": [0b11110, 0b10001, 0b10001, 0b11110, 0b10100, 0b10010, 0b10001],
    "S": [0b01110, 0b10001, 0b10000, 0b01110, 0b00001, 0b10001, 0b01110],
    "T": [0b11111, 0b00100, 0b00100, 0b00100, 0b00100, 0b00100, 0b00100],
    "U": [0b10001, 0b10001, 0b10001, 0b10001, 0b10001, 0b10001, 0b01110],
    "V": [0b10001, 0b10001, 0b10001, 0b10001, 0b10001, 0b01010, 0b00100],
    "W": [0b10001, 0b10001, 0b10001, 0b10101, 0b10101, 0b11011, 0b10001],
    "X": [0b10001, 0b10001, 0b01010, 0b00100, 0b01010, 0b10001, 0b10001],
    "Y": [0b10001, 0b10001, 0b01010, 0b00100, 0b00100, 0b00100, 0b00100],
    "Z": [0b11111, 0b00001, 0b00010, 0b00100, 0b01000, 0b10000, 0b11111],
    "a": [0b00000, 0b00000, 0b01110, 0b00001, 0b01111, 0b10001, 0b01111],
    "b": [0b10000, 0b10000, 0b10110, 0b11001, 0b10001, 0b10001, 0b11110],
    "c": [0b00000, 0b00000, 0b01110, 0b10000, 0b10000, 0b10001, 0b01110],
    "d": [0b00001, 0b00001, 0b01101, 0b10011, 0b10001, 0b10001, 0b01111],
    "e": [0b00000, 0b00000, 0b01110, 0b10001, 0b11111, 0b10000, 0b01110],
    "f": [0b00110, 0b01001, 0b01000, 0b11100, 0b01000, 0b01000, 0b01000],
    "g": [0b00000, 0b01111, 0b10001, 0b10001, 0b01111, 0b00001, 0b01110],
    "h": [0b10000, 0b10000, 0b10110, 0b11001, 0b10001, 0b10001, 0b10001],
    "i": [0b00100, 0b00000, 0b01100, 0b00100, 0b00100, 0b00100, 0b01110],
    "j": [0b00010, 0b00000, 0b00110, 0b00010, 0b00010, 0b10010, 0b01100],
    "k": [0b10000, 0b10000, 0b10010, 0b10100, 0b11000, 0b10100, 0b10010],
    "l": [0b01100, 0b00100, 0b00100, 0b00100, 0b00100, 0b00100, 0b01110],
    "m": [0b00000, 0b00000, 0b11010, 0b10101, 0b10101, 0b10001, 0b10001],
    "n": [0b00000, 0b00000, 0b10110, 0b11001, 0b10001, 0b10001, 0b10001],
    "o": [0b00000, 0b00000, 0b01110, 0b10001, 0b10001, 0b10001, 0b01110],
    "p": [0b00000, 0b00000, 0b11110, 0b10001, 0b11110, 0b10000, 0b10000],
    "q": [0b00000, 0b00000, 0b01101, 0b10011, 0b01111, 0b00001, 0b00001],
    "r": [0b00000, 0b00000, 0b10110, 0b11001, 0b10000, 0b10000, 0b10000],
    "s": [0b00000, 0b00000, 0b01110, 0b10000, 0b01110, 0b00001, 0b11110],
    "t": [0b01000, 0b01000, 0b11100, 0b01000, 0b01000, 0b01001, 0b00110],
    "u": [0b00000, 0b00000, 0b10001, 0b10001, 0b10001, 0b10011, 0b01101],
    "v": [0b00000, 0b00000, 0b10001, 0b10001, 0b10001, 0b01010, 0b00100],
    "w": [0b00000, 0b00000, 0b10001, 0b10001, 0b10101, 0b10101, 0b01010],
    "x": [0b00000, 0b00000, 0b10001, 0b01010, 0b00100, 0b01010, 0b10001],
    "y": [0b00000, 0b00000, 0b10001, 0b10001, 0b01111, 0b00001, 0b01110],
    "z": [0b00000, 0b00000, 0b11111, 0b00010, 0b00100, 0b01000, 0b11111],
    "0": [0b01110, 0b10001, 0b10011, 0b10101, 0b11001, 0b10001, 0b01110],
    "1": [0b00100, 0b01100, 0b00100, 0b00100, 0b00100, 0b00100, 0b01110],
    "2": [0b01110, 0b10001, 0b00001, 0b00010, 0b00100, 0b01000, 0b11111],
    "3": [0b01110, 0b10001, 0b00001, 0b00110, 0b00001, 0b10001, 0b01110],
    "4": [0b00010, 0b00110, 0b01010, 0b10010, 0b11111, 0b00010, 0b00010],
    "5": [0b11111, 0b10000, 0b11110, 0b00001, 0b00001, 0b10001, 0b01110],
    "6": [0b00110, 0b01000, 0b10000, 0b11110, 0b10001, 0b10001, 0b01110],
    "7": [0b11111, 0b00001, 0b00010, 0b00100, 0b01000, 0b01000, 0b01000],
    "8": [0b01110, 0b10001, 0b10001, 0b01110, 0b10001, 0b10001, 0b01110],
    "9": [0b01110, 0b10001, 0b10001, 0b01111, 0b00001, 0b00010, 0b01100],
    " ": [0b00000, 0b00000, 0b00000, 0b00000, 0b00000, 0b00000, 0b00000],
    "!": [0b00100, 0b00100, 0b00100, 0b00100, 0b00100, 0b00000, 0b00100],
    ".": [0b00000, 0b00000, 0b00000, 0b00000, 0b00000, 0b00000, 0b00100],
    ",": [0b00000, 0b00000, 0b00000, 0b00000, 0b00000, 0b00100, 0b01000],
    "-": [0b00000, 0b00000, 0b00000, 0b11111, 0b00000, 0b00000, 0b00000],
    "'": [0b00100, 0b00100, 0b01000, 0b00000, 0b00000, 0b00000, 0b00000],
    ":": [0b00000, 0b00100, 0b00000, 0b00000, 0b00000, 0b00100, 0b00000],
    "?": [0b01110, 0b10001, 0b00001, 0b00110, 0b00100, 0b00000, 0b00100],
    "#": [0b01010, 0b01010, 0b11111, 0b01010, 0b11111, 0b01010, 0b01010],
}

RAINBOW = [
    (255, 80, 80),    # red
    (255, 160, 50),   # orange
    (255, 255, 60),   # yellow
    (80, 255, 80),    # green
    (80, 180, 255),   # blue
    (180, 100, 255),  # purple
    (255, 100, 200),  # pink
]


def _pixel_text_width(text: str, char_w: int = 5, spacing: int = 1) -> int:
    """Width of a string in pixels using the bitmap font."""
    if not text:
        return 0
    return len(text) * char_w + (len(text) - 1) * spacing


def _wrap_words(text: str, max_w: int, char_w: int = 5, spacing: int = 1) -> list[str]:
    """Word-wrap text to fit within max_w pixels."""
    words = text.split()
    lines: list[str] = []
    cur = ""
    for word in words:
        test = f"{cur} {word}" if cur else word
        if _pixel_text_width(test, char_w, spacing) <= max_w:
            cur = test
        else:
            if cur:
                lines.append(cur)
            cur = word
    if cur:
        lines.append(cur)
    return lines


def make_text_image(text: str) -> Image.Image:
    """Create image with text using a pixel-perfect 5x7 bitmap font."""
    img = Image.new("RGB", (DISPLAY_SIZE, DISPLAY_SIZE), (0, 0, 0))

    char_w, char_h = 5, 7
    spacing = 1
    line_gap = 3

    lines = _wrap_words(text, DISPLAY_SIZE, char_w, spacing)

    total_h = len(lines) * char_h + (len(lines) - 1) * line_gap
    y_start = (DISPLAY_SIZE - total_h) // 2

    color_idx = 0
    for line_num, line in enumerate(lines):
        line_w = _pixel_text_width(line, char_w, spacing)
        x_start = (DISPLAY_SIZE - line_w) // 2
        y = y_start + line_num * (char_h + line_gap)

        cx = x_start
        for ch in line:
            glyph = PIXEL_FONT_5x7.get(ch)
            if glyph is None:
                cx += char_w + spacing
                color_idx += 1
                continue
            if ch == " ":
                cx += char_w + spacing
                continue
            color = RAINBOW[color_idx % len(RAINBOW)]
            for row in range(char_h):
                for col in range(char_w):
                    if glyph[row] & (1 << (char_w - 1 - col)):
                        px, py = cx + col, y + row
                        if 0 <= px < DISPLAY_SIZE and 0 <= py < DISPLAY_SIZE:
                            img.putpixel((px, py), color)
            cx += char_w + spacing
            color_idx += 1

    return img


def make_resolution_grid(size: int) -> Image.Image:
    """Create a grid pattern labeled with the resolution size."""
    img = Image.new("RGB", (size, size), (0, 0, 0))
    draw = ImageDraw.Draw(img)

    # White 1px grid lines every 8 pixels
    for i in range(0, size, 8):
        draw.line([(i, 0), (i, size - 1)], fill=(255, 255, 255), width=1)
        draw.line([(0, i), (size - 1, i)], fill=(255, 255, 255), width=1)

    # Draw resolution number in top-left corner with black background for readability
    label = str(size)
    font_size = max(8, size // 4)
    try:
        font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", font_size)
    except Exception:
        font = ImageFont.load_default()

    bbox = draw.textbbox((0, 0), label, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    # Black rectangle behind text
    draw.rectangle([(1, 1), (tw + 4, th + 4)], fill=(0, 0, 0))
    draw.text((2, 2), label, fill=(255, 255, 255), font=font)

    return img


def image_to_gif_at_size(img: Image.Image, size: int) -> bytes:
    """Convert image to GIF bytes at a specific size (ignoring DISPLAY_SIZE)."""
    img = img.convert("RGB").resize((size, size), Image.LANCZOS)
    buf = BytesIO()
    img.save(buf, format="GIF")
    return buf.getvalue()


async def send_image_data(client: BleakClient, gif_data: bytes, label: str):
    """Send GIF data to the backpack (shared logic)."""
    chunk_size = 196
    num_chunks = (len(gif_data) + chunk_size - 1) // chunk_size
    print(f"{label}: GIF {len(gif_data)} bytes, {num_chunks} chunk(s)")

    await send_wait(client, READY)

    for idx in range(num_chunks):
        chunk = gif_data[idx * chunk_size : (idx + 1) * chunk_size]
        pkt = build_image_chunk(idx, chunk, num_chunks)
        status = await send_wait(client, pkt)
        if status != 0:
            print(f"  Warning: chunk {idx} status={status}")
        await asyncio.sleep(0.3)

    await send_wait(client, FINALIZE)


async def test_resolution(test_sizes: list[int] = [32, 48, 64]):
    """Send grid patterns to determine display resolution."""

    print("Scanning for backpack...")
    device = await BleakScanner.find_device_by_filter(
        lambda d, adv: (adv.local_name or "").startswith(DEVICE_NAME_PREFIX),
        timeout=10,
    )
    if not device:
        print("Backpack not found! Is it powered on?")
        return

    print(f"Found: {device.name}")

    async with BleakClient(device) as client:
        await client.start_notify(NOTIFY_UUID, notification_handler)
        print(f"Connected (MTU: {client.mtu_size})")

        for size in test_sizes:
            grid = make_resolution_grid(size)
            gif_data = image_to_gif_at_size(grid, size)
            await send_image_data(client, gif_data, f"Testing {size}x{size}")
            print(f"\n>>> Sent {size}x{size} grid. Look at the backpack!")
            print(f"    Does it show a clean grid with \"{size}\" in the corner?")
            input("    Press Enter to try next size... ")

        await client.stop_notify(NOTIFY_UUID)

    print("\nDone! Update DISPLAY_SIZE in display.py to the size that looked correct.")


async def display_image(img: Image.Image):
    """Send image to the backpack."""
    gif_data = image_to_gif(img)

    chunk_size = 196
    num_chunks = (len(gif_data) + chunk_size - 1) // chunk_size
    print(f"Image: {DISPLAY_SIZE}x{DISPLAY_SIZE}, GIF: {len(gif_data)} bytes, {num_chunks} chunk(s)")

    print("Scanning for backpack...")
    device = await BleakScanner.find_device_by_filter(
        lambda d, adv: (adv.local_name or "").startswith(DEVICE_NAME_PREFIX),
        timeout=10,
    )
    if not device:
        print("Backpack not found! Is it powered on?")
        return

    print(f"Found: {device.name}")

    async with BleakClient(device) as client:
        await client.start_notify(NOTIFY_UUID, notification_handler)
        print(f"Connected (MTU: {client.mtu_size})")

        # Ready
        await send_wait(client, READY)

        # Send image chunks, waiting for ACK after each
        for idx in range(num_chunks):
            chunk = gif_data[idx * chunk_size : (idx + 1) * chunk_size]
            pkt = build_image_chunk(idx, chunk, num_chunks)
            status = await send_wait(client, pkt)
            if status != 0:
                print(f"  Warning: chunk {idx} status={status}")
            await asyncio.sleep(0.3)

        # Finalize
        await send_wait(client, FINALIZE)
        await client.stop_notify(NOTIFY_UUID)

    print("Done! Image should be displayed on the backpack.")


def main():
    args = sys.argv[1:]

    if args and args[0] == "--test-resolution":
        sizes = [int(s) for s in args[1:]] if len(args) > 1 else [32, 48, 64]
        asyncio.run(test_resolution(sizes))
        return

    if not args:
        img = make_test_pattern()
        print("Displaying rainbow test pattern")
    elif args[0] == "--color" and len(args) > 1:
        img = make_solid_color(args[1])
        print(f"Displaying solid color: {args[1]}")
    elif args[0] == "--text" and len(args) > 1:
        img = make_text_image(args[1])
        print(f"Displaying text: {args[1]}")
    elif Path(args[0]).is_file():
        img = Image.open(args[0])
        print(f"Displaying image: {args[0]}")
    else:
        print(f"File not found or unknown option: {args[0]}")
        print(__doc__)
        return

    asyncio.run(display_image(img))


if __name__ == "__main__":
    main()
