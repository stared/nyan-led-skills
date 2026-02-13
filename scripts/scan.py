"""Scan for nearby BLE devices. Run with: uv run scripts/scan.py"""

import asyncio
from bleak import BleakScanner


async def main():
    print("Scanning for BLE devices (10 seconds)...\n")
    devices = await BleakScanner.discover(timeout=10, return_adv=True)

    print(f"Found {len(devices)} devices:\n")
    print(f"{'Name':<30} {'Address':<20} {'RSSI':>5}  {'UUIDs'}")
    print("-" * 100)

    for address, (device, adv_data) in sorted(
        devices.items(), key=lambda x: x[1][1].rssi or -999, reverse=True
    ):
        name = adv_data.local_name or device.name or "(unknown)"
        rssi = adv_data.rssi or 0
        uuids = ", ".join(adv_data.service_uuids) if adv_data.service_uuids else ""
        mfr = (
            ", ".join(f"0x{k:04x}: {v.hex()}" for k, v in adv_data.manufacturer_data.items())
            if adv_data.manufacturer_data
            else ""
        )

        print(f"{name:<30} {address:<20} {rssi:>5}  {uuids}")
        if mfr:
            print(f"  └─ manufacturer_data: {mfr}")


asyncio.run(main())
