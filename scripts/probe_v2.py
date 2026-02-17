"""Probe v2: Systematic investigation of CLEAR, animated GIF, and FINALIZE behavior.

Phase 1: Sequential uploads with CLEAR between them
Phase 2: Sequential uploads WITHOUT CLEAR (confirm it's needed)
Phase 3: Animated GIF (proper multi-frame)
Phase 4: FINALIZE first byte with multi-chunk images
Phase 5: frame_count byte override in chunk header

Usage:
  uv run scripts/probe_v2.py              # Run all phases
  uv run scripts/probe_v2.py 1            # Run phase 1 only
  uv run scripts/probe_v2.py 3 4          # Run phases 3 and 4
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
    CONST_SEQ,
    DEVICE_NAME_PREFIX,
    DISPLAY_SIZE,
    NOTIFY_UUID,
    PAYLOAD_LEN_MARKER,
    READY,
    WRITE_UUID,
    build_image_chunk,
    image_to_gif,
    make_cmd,
    make_packet,
    send_wait,
)

# --- Enhanced notification handler (full hex dump) ---

ack_event = asyncio.Event()
last_status = -1


def verbose_notification_handler(sender, data: bytearray):
    global last_status
    # Import and update the module-level ack_event in display.py too
    import display

    display.ack_event.set()
    display.last_status = -1

    hex_str = data.hex(" ")
    if len(data) >= 11 and data[0] == 0xAA and data[1] == 0x55:
        echo = (data[5] << 8) | data[6]
        last_status = data[10]
        display.last_status = last_status
        st = "OK" if last_status == 0 else f"ERR=0x{last_status:02x}"
        print(f"  ← [{hex_str}] echo=0x{echo:04x} {st}")
    else:
        last_status = -1
        print(f"  ← [{hex_str}] (unknown format)")


# --- CLEAR command ---
CLEAR = make_cmd(0x0009, 0x0802, b"\x00\xff")


# --- Custom chunk builder (override frame_count independently) ---


def build_image_chunk_custom(
    chunk_idx: int, gif_chunk: bytes, total_chunks: int, frame_count_override: int
) -> bytes:
    """Build image chunk with frame_count set independently of total_chunks."""
    idx_bytes = bytes([0x00, chunk_idx, 0x00])
    padded = gif_chunk + b"\x00" * max(0, 196 - len(gif_chunk))
    payload = (
        idx_bytes
        + CONST_SEQ
        + bytes([frame_count_override])  # override frame_count
        + idx_bytes
        + CONST2
        + PAYLOAD_LEN_MARKER
        + padded[:196]
    )
    return make_packet(payload)


# --- Animated GIF creation ---


def make_animated_gif(
    frames: list[Image.Image], duration_ms: int = 500
) -> bytes:
    """Create animated GIF from multiple PIL frames."""
    resized = [f.convert("RGB").resize((DISPLAY_SIZE, DISPLAY_SIZE), Image.LANCZOS) for f in frames]
    buf = BytesIO()
    resized[0].save(
        buf,
        format="GIF",
        save_all=True,
        append_images=resized[1:],
        duration=duration_ms,
        loop=0,
    )
    return buf.getvalue()


# --- Helpers ---

CHUNK_SIZE = 196


def solid(color: tuple[int, int, int]) -> Image.Image:
    return Image.new("RGB", (DISPLAY_SIZE, DISPLAY_SIZE), color)


async def upload_image(
    client: BleakClient,
    gif_data: bytes,
    label: str,
    finalize_args: bytes = b"\x01\x00\x00",
):
    """Standard upload: READY → chunks → FINALIZE."""
    num_chunks = (len(gif_data) + CHUNK_SIZE - 1) // CHUNK_SIZE
    print(f"\n  [{label}] GIF {len(gif_data)} bytes, {num_chunks} chunk(s), "
          f"FINALIZE args={finalize_args.hex(' ')}")

    status = await send_wait(client, READY)
    print(f"  READY → status={status}")

    for idx in range(num_chunks):
        chunk = gif_data[idx * CHUNK_SIZE : (idx + 1) * CHUNK_SIZE]
        pkt = build_image_chunk(idx, chunk, num_chunks)
        status = await send_wait(client, pkt)
        if status != 0:
            print(f"  chunk {idx}/{num_chunks} → ERR status={status}")
        await asyncio.sleep(0.3)

    finalize = make_cmd(0x000F, 0x3603, finalize_args)
    status = await send_wait(client, finalize)
    print(f"  FINALIZE → status={status}")
    return status


async def send_clear(client: BleakClient):
    """Send CLEAR command."""
    print("\n  [CLEAR] Sending clear command...")
    status = await send_wait(client, CLEAR)
    print(f"  CLEAR → status={status}")
    return status


def make_rainbow_gradient() -> Image.Image:
    """Create a detailed rainbow gradient (produces multi-chunk GIF)."""
    img = Image.new("RGB", (DISPLAY_SIZE, DISPLAY_SIZE))
    for y in range(DISPLAY_SIZE):
        for x in range(DISPLAY_SIZE):
            r = int(255 * x / DISPLAY_SIZE)
            g = int(255 * y / DISPLAY_SIZE)
            b = int(255 * (DISPLAY_SIZE - x) / DISPLAY_SIZE)
            img.putpixel((x, y), (r, g, b))
    return img


# --- Phases ---


async def phase1(client: BleakClient):
    """Phase 1: Sequential uploads WITH CLEAR between them."""
    print("\n" + "=" * 60)
    print("PHASE 1: Sequential uploads with CLEAR between them")
    print("Expected: RED appears, then BLUE replaces it")
    print("=" * 60)

    red_gif = image_to_gif(solid((255, 0, 0)))
    blue_gif = image_to_gif(solid((0, 0, 255)))

    # Upload RED
    await upload_image(client, red_gif, "RED")
    print("\n  >>> Observe backpack for 5s — should show RED")
    await asyncio.sleep(5)

    # CLEAR
    await send_clear(client)
    print("  >>> Waiting 2s after CLEAR...")
    await asyncio.sleep(2)

    # Upload BLUE
    await upload_image(client, blue_gif, "BLUE")
    print("\n  >>> Observe backpack for 5s — should show BLUE")
    await asyncio.sleep(5)


async def phase2(client: BleakClient):
    """Phase 2: Sequential uploads WITHOUT CLEAR (expect failure)."""
    print("\n" + "=" * 60)
    print("PHASE 2: Sequential uploads WITHOUT CLEAR")
    print("Expected: RED appears, then GREEN fails to replace (stays RED)")
    print("=" * 60)

    red_gif = image_to_gif(solid((255, 0, 0)))
    green_gif = image_to_gif(solid((0, 255, 0)))

    # Upload RED
    await upload_image(client, red_gif, "RED")
    print("\n  >>> Observe backpack for 5s — should show RED")
    await asyncio.sleep(5)

    # Upload GREEN directly (no CLEAR)
    await upload_image(client, green_gif, "GREEN (no CLEAR)")
    print("\n  >>> Observe backpack for 5s — does it stay RED or show GREEN?")
    await asyncio.sleep(5)

    # Cleanup: CLEAR for next phase
    await send_clear(client)
    await asyncio.sleep(2)


async def phase3(client: BleakClient):
    """Phase 3: Animated GIF (multi-frame) with different delays."""
    print("\n" + "=" * 60)
    print("PHASE 3: Animated GIF (proper multi-frame)")
    print("Expected: Backpack cycles between RED and BLUE frames")
    print("=" * 60)

    red = solid((255, 0, 0))
    blue = solid((0, 0, 255))

    for delay_ms in [500, 100, 2000]:
        anim_gif = make_animated_gif([red, blue], duration_ms=delay_ms)
        num_chunks = (len(anim_gif) + CHUNK_SIZE - 1) // CHUNK_SIZE
        print(f"\n  Animated GIF: delay={delay_ms}ms, size={len(anim_gif)} bytes, {num_chunks} chunks")

        await upload_image(client, anim_gif, f"Anim {delay_ms}ms")
        print(f"\n  >>> Observe backpack for 8s — does it animate? Delay={delay_ms}ms")
        await asyncio.sleep(8)

        await send_clear(client)
        await asyncio.sleep(2)


async def phase4(client: BleakClient):
    """Phase 4: FINALIZE first byte with multi-chunk image."""
    print("\n" + "=" * 60)
    print("PHASE 4: FINALIZE first byte variations (multi-chunk image)")
    print("Expected: Determine if first byte must match chunk count")
    print("=" * 60)

    rainbow = make_rainbow_gradient()
    rainbow_gif = image_to_gif(rainbow)
    num_chunks = (len(rainbow_gif) + CHUNK_SIZE - 1) // CHUNK_SIZE
    print(f"  Rainbow GIF: {len(rainbow_gif)} bytes, {num_chunks} chunks")

    finalize_variants = [
        (b"\x01\x00\x00", "FINALIZE 01 00 00 (standard)"),
        (bytes([num_chunks, 0x00, 0x00]), f"FINALIZE {num_chunks:02x} 00 00 (= chunk count)"),
        (b"\x00\x00\x00", "FINALIZE 00 00 00"),
        (b"\x02\x00\x00", "FINALIZE 02 00 00"),
    ]

    for args, desc in finalize_variants:
        await upload_image(client, rainbow_gif, desc, finalize_args=args)
        print(f"\n  >>> Observe backpack for 5s — {desc}")
        await asyncio.sleep(5)

        await send_clear(client)
        await asyncio.sleep(2)


async def phase5(client: BleakClient):
    """Phase 5: Override frame_count byte in chunk header."""
    print("\n" + "=" * 60)
    print("PHASE 5: frame_count byte override in chunk header")
    print("Expected: Determine if device checks frame_count vs actual chunk count")
    print("=" * 60)

    rainbow = make_rainbow_gradient()
    rainbow_gif = image_to_gif(rainbow)
    num_chunks = (len(rainbow_gif) + CHUNK_SIZE - 1) // CHUNK_SIZE
    print(f"  Rainbow GIF: {len(rainbow_gif)} bytes, {num_chunks} chunks")

    if num_chunks < 2:
        print("  WARNING: Rainbow GIF is only 1 chunk — this test needs multi-chunk.")
        print("  Skipping phase 5.")
        return

    # Test A: frame_count=1 but send all chunks (should the device reject after first?)
    print(f"\n  Test A: frame_count=1 (lying), actual chunks={num_chunks}")
    status = await send_wait(client, READY)
    print(f"  READY → status={status}")

    for idx in range(num_chunks):
        chunk = rainbow_gif[idx * CHUNK_SIZE : (idx + 1) * CHUNK_SIZE]
        pkt = build_image_chunk_custom(idx, chunk, num_chunks, frame_count_override=1)
        status = await send_wait(client, pkt)
        st = "OK" if status == 0 else f"ERR=0x{status:02x}"
        print(f"  chunk {idx}/{num_chunks} (frame_count=1) → {st}")
        await asyncio.sleep(0.3)

    finalize = make_cmd(0x000F, 0x3603, b"\x01\x00\x00")
    status = await send_wait(client, finalize)
    print(f"  FINALIZE → status={status}")
    print(f"\n  >>> Observe backpack for 5s — did it display anything?")
    await asyncio.sleep(5)

    await send_clear(client)
    await asyncio.sleep(2)

    # Test B: frame_count=num_chunks (matching), same data
    print(f"\n  Test B: frame_count={num_chunks} (correct), actual chunks={num_chunks}")
    status = await send_wait(client, READY)
    print(f"  READY → status={status}")

    for idx in range(num_chunks):
        chunk = rainbow_gif[idx * CHUNK_SIZE : (idx + 1) * CHUNK_SIZE]
        pkt = build_image_chunk_custom(idx, chunk, num_chunks, frame_count_override=num_chunks)
        status = await send_wait(client, pkt)
        st = "OK" if status == 0 else f"ERR=0x{status:02x}"
        print(f"  chunk {idx}/{num_chunks} (frame_count={num_chunks}) → {st}")
        await asyncio.sleep(0.3)

    finalize = make_cmd(0x000F, 0x3603, b"\x01\x00\x00")
    status = await send_wait(client, finalize)
    print(f"  FINALIZE → status={status}")
    print(f"\n  >>> Observe backpack for 5s — did it display correctly?")
    await asyncio.sleep(5)

    await send_clear(client)
    await asyncio.sleep(2)


# --- Main ---

PHASES = {
    1: ("Sequential uploads WITH CLEAR", phase1),
    2: ("Sequential uploads WITHOUT CLEAR", phase2),
    3: ("Animated GIF (multi-frame)", phase3),
    4: ("FINALIZE first byte variations", phase4),
    5: ("frame_count byte override", phase5),
}


async def main():
    # Parse phase selection
    args = sys.argv[1:]
    if args:
        selected = [int(a) for a in args]
    else:
        selected = list(PHASES.keys())

    print("=" * 60)
    print("PROBE V2: Systematic BLE display investigation")
    print(f"Display size: {DISPLAY_SIZE}x{DISPLAY_SIZE}")
    print(f"Phases to run: {selected}")
    print("=" * 60)

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
        await client.start_notify(NOTIFY_UUID, verbose_notification_handler)
        print(f"Connected (MTU: {client.mtu_size})")

        for phase_num in selected:
            if phase_num not in PHASES:
                print(f"\nUnknown phase {phase_num}, skipping.")
                continue
            desc, func = PHASES[phase_num]
            print(f"\n{'#' * 60}")
            print(f"# Starting Phase {phase_num}: {desc}")
            print(f"{'#' * 60}")
            await func(client)

        await client.stop_notify(NOTIFY_UUID)

    print("\n" + "=" * 60)
    print("ALL PHASES COMPLETE")
    print("=" * 60)


asyncio.run(main())
