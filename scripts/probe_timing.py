"""Probe animation timing via CONST_SEQ variation and GIF frame delays.

Tests whether:
1. Modifying bytes in CONST_SEQ changes animation speed
2. GIF's own frame delay metadata is respected by the device

Usage:
  uv run scripts/probe_timing.py
"""

import asyncio
import sys
from io import BytesIO
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from bleak import BleakClient, BleakScanner
from PIL import Image

from display import (
    CONST2,
    DEVICE_NAME_PREFIX,
    DISPLAY_SIZE,
    NOTIFY_UUID,
    PAYLOAD_LEN_MARKER,
    READY,
    WRITE_UUID,
    make_cmd,
    make_packet,
    notification_handler,
    send_wait,
)

# Default CONST_SEQ for reference:
# c1 02 09 01 01 0c 01 00 0d 01 00 0e 01 00 14 03 01 09 0a 11 04 00 01 00 0a 12 07
# idx: 0  1  2  3  4  5  6  7  8  9 10 11 12 13 14 15 16 17 18 19 20 21 22 23 24 25 26
DEFAULT_CONST_SEQ = bytes.fromhex("c1020901010c01000d01000e0100140301090a11040001000a1207")


def make_animated_gif(color1: tuple, color2: tuple, frame_delay_ms: int = 100) -> bytes:
    """Create a 2-frame animated GIF alternating between two colors."""
    frame1 = Image.new("RGB", (DISPLAY_SIZE, DISPLAY_SIZE), color1)
    frame2 = Image.new("RGB", (DISPLAY_SIZE, DISPLAY_SIZE), color2)
    buf = BytesIO()
    frame1.save(
        buf,
        format="GIF",
        save_all=True,
        append_images=[frame2],
        duration=frame_delay_ms,
        loop=0,
    )
    return buf.getvalue()


def build_image_chunk_custom_seq(
    chunk_idx: int, gif_chunk: bytes, total_chunks: int, const_seq: bytes
) -> bytes:
    """Build image data chunk with a custom CONST_SEQ."""
    idx_bytes = bytes([0x00, chunk_idx, 0x00])
    padded = gif_chunk + b"\x00" * max(0, 196 - len(gif_chunk))
    payload = (
        idx_bytes
        + const_seq
        + bytes([total_chunks])
        + idx_bytes
        + CONST2
        + PAYLOAD_LEN_MARKER
        + padded[:196]
    )
    return make_packet(payload)


FINALIZE = make_cmd(0x000F, 0x3603, b"\x01\x00\x00")


async def send_gif_with_seq(
    client: BleakClient, gif_data: bytes, const_seq: bytes, label: str
):
    """Send a GIF using a custom CONST_SEQ."""
    chunk_size = 196
    num_chunks = (len(gif_data) + chunk_size - 1) // chunk_size

    print(f"\n--- {label} ---")
    print(f"  CONST_SEQ: {const_seq.hex(' ')}")
    print(f"  GIF: {len(gif_data)} bytes, {num_chunks} chunk(s)")

    await send_wait(client, READY)

    for idx in range(num_chunks):
        chunk = gif_data[idx * chunk_size : (idx + 1) * chunk_size]
        pkt = build_image_chunk_custom_seq(idx, chunk, num_chunks, const_seq)
        status = await send_wait(client, pkt)
        if status != 0:
            print(f"  Warning: chunk {idx} status={status}")
        await asyncio.sleep(0.3)

    status = await send_wait(client, FINALIZE)
    print(f"  FINALIZE status: {status}")
    return status


def modify_seq(offset: int, value: int) -> bytes:
    """Create a modified CONST_SEQ with one byte changed."""
    seq = bytearray(DEFAULT_CONST_SEQ)
    seq[offset] = value
    return bytes(seq)


async def main():
    print("=== Probe: Animation Timing via CONST_SEQ and GIF Frame Delay ===")
    print(f"Display size: {DISPLAY_SIZE}x{DISPLAY_SIZE}")
    print(f"Default CONST_SEQ ({len(DEFAULT_CONST_SEQ)} bytes):")
    print(f"  {DEFAULT_CONST_SEQ.hex(' ')}")

    # Candidate byte offsets to test (with their default values):
    # offset 8-9:  0d 01  (might be timing-related)
    # offset 12-13: 0e 01 (might be timing-related)
    # offset 14-15: 00 14 (0x14 = 20, could be frame delay)
    # offset 17-18: 09 0a (could be animation parameters)
    # offset 24-25: 00 0a (0x0a = 10, could be frame count or delay)

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

        # ---- Part A: Test GIF frame delay metadata ----
        print("\n" + "=" * 60)
        print("PART A: Does the GIF's own frame delay matter?")
        print("=" * 60)

        gif_fast = make_animated_gif((255, 0, 0), (0, 0, 255), frame_delay_ms=50)
        await send_gif_with_seq(
            client, gif_fast, DEFAULT_CONST_SEQ,
            "A1: Animated GIF RED↔BLUE, 50ms frame delay"
        )
        input("\n  >>> Observe animation speed. Press Enter...")

        gif_medium = make_animated_gif((255, 0, 0), (0, 0, 255), frame_delay_ms=500)
        await send_gif_with_seq(
            client, gif_medium, DEFAULT_CONST_SEQ,
            "A2: Animated GIF RED↔BLUE, 500ms frame delay"
        )
        input("\n  >>> Faster, slower, or same as before? Press Enter...")

        gif_slow = make_animated_gif((255, 0, 0), (0, 0, 255), frame_delay_ms=2000)
        await send_gif_with_seq(
            client, gif_slow, DEFAULT_CONST_SEQ,
            "A3: Animated GIF RED↔BLUE, 2000ms frame delay"
        )
        input("\n  >>> Faster, slower, or same? Press Enter...")

        # ---- Part B: Vary CONST_SEQ bytes ----
        print("\n" + "=" * 60)
        print("PART B: Vary CONST_SEQ bytes (using 500ms GIF)")
        print("=" * 60)

        # Use the medium-speed GIF as baseline for all CONST_SEQ tests
        gif_test = gif_medium

        # Baseline with default
        await send_gif_with_seq(
            client, gif_test, DEFAULT_CONST_SEQ,
            "B0: Baseline — default CONST_SEQ"
        )
        input("\n  >>> Note the animation speed (baseline). Press Enter...")

        # Test candidates: (offset, test_value, description)
        candidates = [
            # offset 14: default 0x00, part of "00 14" pair
            (14, 0x01, "offset 14: 0x00→0x01 (in '00 14' pair)"),
            (14, 0x50, "offset 14: 0x00→0x50"),
            # offset 15: default 0x14=20
            (15, 0x01, "offset 15 (0x14→0x01, was 20 decimal)"),
            (15, 0x05, "offset 15 (0x14→0x05)"),
            (15, 0x50, "offset 15 (0x14→0x50)"),
            (15, 0xFF, "offset 15 (0x14→0xFF)"),
            # offset 8: default 0x0d=13
            (8, 0x01, "offset 8 (0x0d→0x01)"),
            (8, 0x50, "offset 8 (0x0d→0x50)"),
            # offset 9: default 0x01
            (9, 0x05, "offset 9 (0x01→0x05)"),
            (9, 0x20, "offset 9 (0x01→0x20)"),
            # offset 17: default 0x09
            (17, 0x01, "offset 17 (0x09→0x01)"),
            (17, 0x50, "offset 17 (0x09→0x50)"),
            # offset 18: default 0x0a=10
            (18, 0x01, "offset 18 (0x0a→0x01)"),
            (18, 0x50, "offset 18 (0x0a→0x50)"),
            # offset 24: default 0x00
            (24, 0x05, "offset 24 (0x00→0x05)"),
            (24, 0x50, "offset 24 (0x00→0x50)"),
            # offset 25: default 0x0a=10
            (25, 0x01, "offset 25 (0x0a→0x01)"),
            (25, 0x50, "offset 25 (0x0a→0x50)"),
        ]

        for i, (offset, value, desc) in enumerate(candidates, 1):
            modified = modify_seq(offset, value)
            status = await send_gif_with_seq(
                client, gif_test, modified,
                f"B{i}: {desc}"
            )
            if status != 0:
                print(f"  *** Device rejected this (status={status}) — likely invalid")
            input(f"\n  >>> Compared to baseline: faster/slower/same/error? Press Enter...")

        # Restore baseline
        await send_gif_with_seq(
            client, gif_test, DEFAULT_CONST_SEQ,
            "RESTORE: Back to default CONST_SEQ"
        )

        await client.stop_notify(NOTIFY_UUID)

    print("\nDone! Review your observations to identify timing-related bytes.")


asyncio.run(main())
