"""Display a custom image on the Nyan Gear backpack.

Usage:
  uv run scripts/display.py                    # Show test pattern
  uv run scripts/display.py image.png          # Show an image file
  uv run scripts/display.py image.gif          # Show a GIF
  uv run scripts/display.py --color red        # Show solid color
  uv run scripts/display.py --color "#00ff00"  # Show hex color
  uv run scripts/display.py --text "HI"        # Show text
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

# Display is 32x32 (confirmed working)
DISPLAY_SIZE = 32

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


def make_text_image(text: str) -> Image.Image:
    """Create image with text."""
    img = Image.new("RGB", (DISPLAY_SIZE, DISPLAY_SIZE), (0, 0, 0))
    draw = ImageDraw.Draw(img)
    font_size = max(8, DISPLAY_SIZE // max(1, len(text)))
    try:
        font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", font_size)
    except Exception:
        font = ImageFont.load_default()

    bbox = draw.textbbox((0, 0), text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    x = (DISPLAY_SIZE - tw) // 2
    y = (DISPLAY_SIZE - th) // 2
    draw.text((x, y), text, fill=(255, 255, 255), font=font)
    return img


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


main()
