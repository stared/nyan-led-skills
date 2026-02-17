"""Probe multiple image slots via FINALIZE args.

The FINALIZE command uses args `01 00 00`. This script tests whether
the first byte is a slot/image index by sending different colored images
with different FINALIZE arg values.

Usage:
  uv run scripts/probe_slots.py
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from bleak import BleakClient, BleakScanner
from PIL import Image

from display import (
    DEVICE_NAME_PREFIX,
    DISPLAY_SIZE,
    NOTIFY_UUID,
    READY,
    WRITE_UUID,
    build_image_chunk,
    image_to_gif,
    make_cmd,
    make_packet,
    notification_handler,
    send_wait,
)


def make_finalize(args: bytes) -> bytes:
    """Build FINALIZE command with custom args."""
    return make_cmd(0x000F, 0x3603, args)


async def send_image_with_finalize(
    client: BleakClient, img: Image.Image, finalize_args: bytes, label: str
):
    """Send an image and finalize with custom args."""
    gif_data = image_to_gif(img)
    chunk_size = 196
    num_chunks = (len(gif_data) + chunk_size - 1) // chunk_size

    print(f"\n--- {label} ---")
    print(f"  FINALIZE args: {finalize_args.hex(' ')}")
    print(f"  GIF: {len(gif_data)} bytes, {num_chunks} chunk(s)")

    # READY
    print("  Sending READY...")
    status = await send_wait(client, READY)
    print(f"  READY status: {status}")

    # Image chunks
    for idx in range(num_chunks):
        chunk = gif_data[idx * chunk_size : (idx + 1) * chunk_size]
        pkt = build_image_chunk(idx, chunk, num_chunks)
        status = await send_wait(client, pkt)
        if status != 0:
            print(f"  Warning: chunk {idx} status={status}")
        await asyncio.sleep(0.3)

    # FINALIZE with custom args
    finalize = make_finalize(finalize_args)
    print(f"  Sending FINALIZE with args {finalize_args.hex(' ')}...")
    status = await send_wait(client, finalize)
    print(f"  FINALIZE status: {status}")

    return status


async def main():
    print("=== Probe: Multiple Image Slots via FINALIZE args ===")
    print(f"Display size: {DISPLAY_SIZE}x{DISPLAY_SIZE}")

    # Create distinct colored images
    colors = {
        "RED": (255, 0, 0),
        "BLUE": (0, 0, 255),
        "GREEN": (0, 255, 0),
        "YELLOW": (255, 255, 0),
        "CYAN": (0, 255, 255),
        "MAGENTA": (255, 0, 255),
    }

    images = {
        name: Image.new("RGB", (DISPLAY_SIZE, DISPLAY_SIZE), color)
        for name, color in colors.items()
    }

    print("\nScanning for backpack...")
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

        PAUSE = 8  # seconds between trials to observe backpack

        trials = [
            ("RED",     b"\x01\x00\x00", "Trial 1: RED image, FINALIZE args 01 00 00 (baseline)"),
            ("BLUE",    b"\x02\x00\x00", "Trial 2: BLUE image, FINALIZE args 02 00 00"),
            ("GREEN",   b"\x03\x00\x00", "Trial 3: GREEN image, FINALIZE args 03 00 00"),
            ("YELLOW",  b"\x00\x00\x00", "Trial 4: YELLOW image, FINALIZE args 00 00 00"),
            ("CYAN",    b"\x01\x01\x00", "Trial 5: CYAN image, FINALIZE args 01 01 00"),
            ("MAGENTA", b"\x01\x00\x01", "Trial 6: MAGENTA image, FINALIZE args 01 00 01"),
        ]

        for color_name, args, label in trials:
            status = await send_image_with_finalize(client, images[color_name], args, label)
            print(f"\n  >>> Waiting {PAUSE}s — observe the backpack...")
            await asyncio.sleep(PAUSE)

        # Trial 7: Multi-image back-to-back without FINALIZE between
        print("\n--- Trial 7: Two images back-to-back, single FINALIZE ---")
        print("  Sending RED image chunks...")
        gif_red = image_to_gif(images["RED"])
        gif_blue = image_to_gif(images["BLUE"])
        chunk_size = 196

        # READY
        await send_wait(client, READY)

        # Send RED chunks
        num_red = (len(gif_red) + chunk_size - 1) // chunk_size
        for idx in range(num_red):
            chunk = gif_red[idx * chunk_size : (idx + 1) * chunk_size]
            pkt = build_image_chunk(idx, chunk, num_red)
            await send_wait(client, pkt)
            await asyncio.sleep(0.3)

        print("  RED chunks sent. Now sending BLUE chunks (continuing index)...")

        # Send BLUE chunks with continuing indices
        num_blue = (len(gif_blue) + chunk_size - 1) // chunk_size
        total = num_red + num_blue
        for idx in range(num_blue):
            chunk = gif_blue[idx * chunk_size : (idx + 1) * chunk_size]
            # Use continuing index and total count
            pkt = build_image_chunk(num_red + idx, chunk, total)
            await send_wait(client, pkt)
            await asyncio.sleep(0.3)

        # Single finalize
        finalize = make_finalize(b"\x01\x00\x00")
        status = await send_wait(client, finalize)
        print(f"  FINALIZE status: {status}")
        print(f"\n  >>> Waiting {PAUSE}s — does it cycle between RED and BLUE?")
        await asyncio.sleep(PAUSE)

        await client.stop_notify(NOTIFY_UUID)

    print("\nDone! Note your observations above.")


asyncio.run(main())
