# Nyan Gear BLE Protocol — Fully Reverse-Engineered

## Device Info
- **Manufacturer**: Shenzhen Yanse Technology
- **Protocol family**: ATOTOZONE-family (reverse-engineered from OverScore article)
- **Device name pattern**: "YS*" (e.g. YS5257111003)
- **Display resolution**: 64x64 pixels (confirmed via grid test pattern)
- **BLE Service**: 0000fff0-0000-1000-8000-00805f9b34fb
- **Write characteristic**: 0000fff2 (write-without-response)
- **Notify characteristic**: 0000fff1 (notifications/ACKs)
- **MTU**: 512

## Packet format

```
aa55ffff <len> <data[len-1 bytes]> <checksum_lo> <checksum_hi>
```

- `aa55ffff` = magic header
- `len` = number of data bytes + 1
- checksum = sum of all bytes from header through data (inclusive) mod 65536
- checksum_lo = checksum & 0xFF
- checksum_hi = (checksum >> 8) & 0xFF

## Commands

### Ready (prepare for image upload)
```
data: 00 09 00 c1 02 08 02 00 00
```

### Clear (reset to default animation)
```
data: 00 09 00 c1 02 08 02 00 ff
```

### Image data chunk
```
data: 00 <idx> 00 <CONST_SEQ:27B> <total_chunks:1B> 00 <idx> 00 <CONST2:4B> 81 c4 <gif_data_padded_to_196B>
```
- CONST_SEQ = c1020901010c01000d01000e0100140301090a11040001000a1207
- CONST2 = c4000013
- `81 c4` = mandatory payload length marker (always this value)
- `total_chunks` = total number of image chunks (MUST be correct)
- `idx` = chunk index (0, 1, 2, ...)
- GIF data padded with zeros to exactly 196 bytes per chunk
- Each chunk packet = 243 bytes total

### Finalize (commit the image to display)
```
data: 00 0f 00 c1 02 36 03 01 00 00
```

## Response format
```
aa55XXXX 07 00 <echo_idx> 00 81 82 <status> <chk_lo> <chk_hi>
```
- XXXX = ffff or 7e7c (both valid)
- echo_idx = echoes the chunk index or command ID
- status: 0x00 = OK, 0x03 = bad format, 0x09 = wrong frame_count

## Upload sequence
1. Send READY
2. For each chunk (0..N-1): send image chunk, wait for ACK
3. Send FINALIZE

## Image format
- GIF format, resized to 64x64 pixels
- Split into 196-byte chunks
- Each chunk wrapped in protocol packet (243 bytes each)
- Wait for ACK (OK status) before sending next chunk
