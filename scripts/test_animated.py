"""Send a single animated GIF (RED↔BLUE) and disconnect. No CLEAR.

If the backpack keeps cycling after disconnect, animated GIF is the answer.
If it shows only the first frame, the device doesn't support GIF animation.

Usage:
  uv run scripts/test_animated.py
  uv run scripts/test_animated.py --delay 1000    # 1s per frame
  uv run scripts/test_animated.py --frames 4      # RED→BLUE→GREEN→YELLOW
"""

import asyncio
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
    READY,
    build_image_chunk,
    image_to_gif,
    make_cmd,
    notification_handler,
    send_wait,
)

CHUNK_SIZE = 196
FINALIZE = make_cmd(0x000F, 0x3603, b"\x01\x00\x00")


def make_animated_gif(frames: list[Image.Image], duration_ms: int) -> bytes:
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


async def main():
    delay_ms = 500
    num_frames = 2

    args = sys.argv[1:]
    i = 0
    while i < len(args):
        if args[i] == "--delay" and i + 1 < len(args):
            delay_ms = int(args[i + 1])
            i += 2
        elif args[i] == "--frames" and i + 1 < len(args):
            num_frames = int(args[i + 1])
            i += 2
        else:
            i += 1

    all_colors = [
        ("RED", (255, 0, 0)),
        ("BLUE", (0, 0, 255)),
        ("GREEN", (0, 255, 0)),
        ("YELLOW", (255, 255, 0)),
        ("CYAN", (0, 255, 255)),
        ("MAGENTA", (255, 0, 255)),
    ]

    colors = all_colors[:num_frames]
    frames = [Image.new("RGB", (DISPLAY_SIZE, DISPLAY_SIZE), c) for _, c in colors]
    names = [n for n, _ in colors]

    gif_data = make_animated_gif(frames, delay_ms)
    num_chunks = (len(gif_data) + CHUNK_SIZE - 1) // CHUNK_SIZE

    print(f"Animated GIF: {' → '.join(names)}, delay={delay_ms}ms")
    print(f"GIF size: {len(gif_data)} bytes, {num_chunks} chunk(s)")

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

        # Upload
        await send_wait(client, READY)

        for idx in range(num_chunks):
            chunk = gif_data[idx * CHUNK_SIZE : (idx + 1) * CHUNK_SIZE]
            pkt = build_image_chunk(idx, chunk, num_chunks)
            status = await send_wait(client, pkt)
            if status != 0:
                print(f"  chunk {idx}/{num_chunks} → ERR status={status}")
            await asyncio.sleep(0.3)

        await send_wait(client, FINALIZE)
        await client.stop_notify(NOTIFY_UUID)

    print("\nDone! Disconnected. Watch the backpack:")
    print("  - If it cycles between colors → animated GIF works!")
    print("  - If it shows only first frame → device doesn't animate GIFs")
    print("  - If it reverts to Nyan → image wasn't stored")


asyncio.run(main())
