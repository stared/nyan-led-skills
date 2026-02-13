# nyan-pack

Control a [Nyan Gear](https://nyangear.com/) LED backpack from your computer via Bluetooth Low Energy.

The backpack is a rebranded product by **Shenzhen Yanse Technology**, sold under many names (Nyan Gear, LOY Bags, Gelrova, KWQ, Welaso, HypeBrother). The official app is [LOY SPACE](https://apps.apple.com/us/app/loy-space/id1636648229). No official API exists — this project reverse-engineers the BLE protocol.

## Usage

```bash
uv run scripts/display.py                    # rainbow test pattern
uv run scripts/display.py --text "HI"        # text
uv run scripts/display.py --color red        # solid color
uv run scripts/display.py --color "#20e0af"  # hex color
uv run scripts/display.py photo.png          # any image file
```

Utility scripts:
```bash
uv run scripts/scan.py       # find BLE devices nearby
uv run scripts/discover.py   # inspect GATT services of the backpack
```

## Setup

Requires Python 3.10+ and [uv](https://docs.astral.sh/uv/):

```bash
uv sync
```

The backpack must be powered on (USB power bank connected) and **not** connected to the LOY SPACE app simultaneously.

## Protocol

See [scripts/protocol_notes.md](scripts/protocol_notes.md) for the full reverse-engineered protocol documentation.

Key facts:
- BLE service `0000fff0`, write char `0000fff2`, notify char `0000fff1`
- Packets use `aa55ffff` header with CheckSum8 Modulo 65536
- Images are sent as GIF data in 196-byte chunks
- Display is 32×32 pixels

## How it was reverse-engineered

No prior public RE existed for this device. The protocol was cracked through:

1. BLE scanning with [bleak](https://github.com/hbldh/bleak) to find the device (name prefix "YS")
2. GATT service discovery (single service, two characteristics)
3. Trying command patterns from similar devices — the [ATOTOZONE LED matrix RE](https://overscore.media/posts/series/matthews-machinations/reverse-engineering-a-ble-led-matrix) by OverScore Media turned out to use a compatible protocol family
4. Trial and error to find correct chunk indexing (`00 <idx> 00`) and frame count

## Open questions

- What is the actual display resolution? We use 32×32 and it works, but the device might support 48×48 or 64×64
- Can animated GIFs be sent (multi-frame)?
- What do the CONST_SEQ bytes actually mean? (`c1020901010c01000d01000e0100140301090a11040001000a1207`)
- Can brightness be controlled via BLE?
- Is there a "read current image" command?
- The `81c4` payload length marker — what does it encode?

## Useful references

- [OverScore Media: Reverse Engineering a BLE LED Matrix](https://overscore.media/posts/series/matthews-machinations/reverse-engineering-a-ble-led-matrix) — closest protocol documentation (ATOTOZONE CI-VIALD19), same `aa55ffff` packet family
- [BK-Light AppBypass](https://github.com/Pupariaa/Bk-Light-AppBypass) — Python BLE toolkit for a similar Chinese LED matrix (different protocol but helpful architecture reference)
- [bleak](https://github.com/hbldh/bleak) — cross-platform Python BLE library
