"""Connect to the Nyan Gear backpack and discover all GATT services/characteristics.

Run with: uv run scripts/discover.py
"""

import asyncio
from bleak import BleakClient, BleakScanner

DEVICE_NAME_PREFIX = "YS"


async def main():
    print(f"Scanning for device with name starting with '{DEVICE_NAME_PREFIX}'...")
    device = await BleakScanner.find_device_by_filter(
        lambda d, adv: (adv.local_name or "").startswith(DEVICE_NAME_PREFIX),
        timeout=10,
    )

    if not device:
        print("Device not found! Make sure the backpack is powered on.")
        return

    print(f"Found: {device.name} ({device.address})")
    print(f"Connecting...\n")

    async with BleakClient(device) as client:
        print(f"Connected: {client.is_connected}")
        print(f"MTU size: {client.mtu_size}\n")

        for service in client.services:
            print(f"Service: {service.uuid} — {service.description}")
            for char in service.characteristics:
                props = ", ".join(char.properties)
                print(f"  Characteristic: {char.uuid} — {char.description}")
                print(f"    Properties: {props}")
                print(f"    Handle: 0x{char.handle:04x}")

                if "read" in char.properties:
                    try:
                        value = await asyncio.wait_for(
                            client.read_gatt_char(char), timeout=3
                        )
                        print(f"    Value: {value} (hex: {value.hex()})")
                    except Exception as e:
                        print(f"    Value: (read failed: {e})")

                # Skip descriptor reads — causes hangs on macOS CoreBluetooth
                if char.descriptors:
                    print(f"    Descriptors: {[d.uuid for d in char.descriptors]}")
            print()

    print("Done.")


asyncio.run(main())
