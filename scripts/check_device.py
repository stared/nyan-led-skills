"""Quick check if the LED backpack is discoverable."""
import asyncio
from bleak import BleakScanner


async def main():
    print("Scanning for YS* devices (10s)...")
    device = await BleakScanner.find_device_by_filter(
        lambda d, adv: (adv.local_name or "").startswith("YS"),
        timeout=10,
    )
    if device:
        print(f"Found backpack: {device.name} ({device.address})")
    else:
        print("Backpack not found. Is it powered on?")


asyncio.run(main())
