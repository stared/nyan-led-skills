"""Śmigus Dyngus / Lany Poniedziałek animation — people pouring water & swinging pussy willows!

Usage:
  uv run scripts/smigus_dyngus.py
"""

import asyncio
import math
import random
import sys
from io import BytesIO
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from bleak import BleakClient, BleakScanner
from PIL import Image, ImageDraw

from display import (
    DEVICE_NAME_PREFIX,
    DISPLAY_SIZE,
    NOTIFY_UUID,
    READY,
    build_image_chunk,
    make_cmd,
    notification_handler,
    send_wait,
)

S = DISPLAY_SIZE  # 64
CHUNK_SIZE = 196
FINALIZE = make_cmd(0x000F, 0x3603, b"\x01\x00\x00")

random.seed(42)

# Colors
BG = (8, 12, 30)
SKIN = (240, 200, 160)
SHIRT_BLUE = (50, 100, 200)
SHIRT_RED = (200, 60, 60)
PANTS = (60, 60, 90)
BUCKET_GRAY = (140, 140, 160)
BRANCH_BROWN = (110, 65, 30)
CATKIN_LIGHT = (215, 215, 200)
CATKIN_MID = (185, 185, 170)

WATER_COLORS = [
    (30, 144, 255),
    (0, 191, 255),
    (70, 210, 255),
    (100, 230, 255),
    (50, 170, 240),
    (20, 120, 220),
]


def draw_stick_person(draw: ImageDraw.Draw, cx: int, foot_y: int, shirt_color: tuple,
                      arm_angle_l: float, arm_angle_r: float):
    """Draw a simple stick person. Arms at given angles (0=down, pi/2=horizontal, pi=up)."""
    # Body proportions
    head_r = 4
    body_len = 14
    arm_len = 10
    leg_len = 10

    head_y = foot_y - leg_len - body_len - head_r * 2
    neck_y = head_y + head_r * 2
    hip_y = neck_y + body_len
    shoulder_y = neck_y + 3

    # Head
    draw.ellipse([cx - head_r, head_y, cx + head_r, head_y + head_r * 2], fill=SKIN)

    # Body
    draw.line([(cx, neck_y), (cx, hip_y)], fill=shirt_color, width=3)

    # Arms
    lax = cx + int(math.cos(math.pi - arm_angle_l) * arm_len)
    lay = shoulder_y - int(math.sin(arm_angle_l) * arm_len)
    rax = cx + int(math.cos(arm_angle_r) * arm_len)
    ray = shoulder_y - int(math.sin(arm_angle_r) * arm_len)
    draw.line([(cx - 1, shoulder_y), (lax, lay)], fill=shirt_color, width=2)
    draw.line([(cx + 1, shoulder_y), (rax, ray)], fill=shirt_color, width=2)

    # Legs
    draw.line([(cx, hip_y), (cx - 4, foot_y)], fill=PANTS, width=2)
    draw.line([(cx, hip_y), (cx + 4, foot_y)], fill=PANTS, width=2)

    return (lax, lay), (rax, ray), (cx, shoulder_y)


def draw_bucket_pour(draw: ImageDraw.Draw, hand_x: int, hand_y: int, tilt: float, pour_phase: float):
    """Draw a bucket at hand position, tilted, with water pouring out."""
    bw, bh = 7, 6
    # Bucket body (simplified as tilted rectangle)
    # tilt: 0 = upright, 1 = fully tipped
    angle = tilt * 1.2

    # Draw bucket as a trapezoid
    cos_a, sin_a = math.cos(angle), math.sin(angle)
    pts = [(-bw // 2, -bh), (bw // 2, -bh), (bw // 2 + 2, 0), (-bw // 2 - 2, 0)]
    rotated = []
    for px, py in pts:
        rx = hand_x + int(px * cos_a - py * sin_a)
        ry = hand_y + int(px * sin_a + py * cos_a)
        rotated.append((rx, ry))
    draw.polygon(rotated, fill=BUCKET_GRAY, outline=(100, 100, 120))

    # Pour spout position (top-right of tilted bucket)
    spout_x = hand_x + int((bw // 2) * cos_a - (-bh) * sin_a)
    spout_y = hand_y + int((bw // 2) * sin_a + (-bh) * cos_a)

    return spout_x, spout_y


def draw_water_stream(draw: ImageDraw.Draw, sx: int, sy: int, phase: float, num_frames: int):
    """Draw water pouring from a point — arc of droplets."""
    if phase < 0.1:
        return
    num_drops = 15
    for i in range(num_drops):
        t = i / num_drops * phase * 1.5
        # Parabolic water arc
        wx = sx + int(t * 6)
        wy = sy + int(t * t * 8)
        if 0 <= wx < S and 0 <= wy < S:
            color = WATER_COLORS[i % len(WATER_COLORS)]
            r = 2 if i < num_drops // 2 else 1
            draw.ellipse([wx - r, wy - r, wx + r, wy + r], fill=color)
    # Extra scattered drops at the end
    for _ in range(8):
        t = phase * 1.5
        wx = sx + int(t * 6 + random.gauss(0, 3))
        wy = sy + int(t * t * 8 + random.gauss(0, 4))
        if 0 <= wx < S and 0 <= wy < S:
            color = WATER_COLORS[random.randint(0, len(WATER_COLORS) - 1)]
            draw.point((wx, wy), fill=color)


def draw_pussy_willow_branch(draw: ImageDraw.Draw, hand_x: int, hand_y: int, swing_angle: float):
    """Draw a pussy willow branch being swung from hand position."""
    branch_len = 22
    # Branch direction based on swing
    end_x = hand_x + int(math.cos(swing_angle) * branch_len)
    end_y = hand_y + int(math.sin(swing_angle) * branch_len)

    # Draw stem with slight curve
    mid_x = (hand_x + end_x) // 2 + int(math.sin(swing_angle) * 4)
    mid_y = (hand_y + end_y) // 2 - int(math.cos(swing_angle) * 4)
    draw.line([(hand_x, hand_y), (mid_x, mid_y)], fill=BRANCH_BROWN, width=2)
    draw.line([(mid_x, mid_y), (end_x, end_y)], fill=BRANCH_BROWN, width=2)

    # Catkins along the branch
    for t in [0.3, 0.45, 0.6, 0.75, 0.9]:
        bx = int(hand_x + (end_x - hand_x) * t)
        by = int(hand_y + (end_y - hand_y) * t)
        # Alternate sides
        side = 1 if int(t * 10) % 2 == 0 else -1
        nx = -math.sin(swing_angle) * side * 4
        ny = math.cos(swing_angle) * side * 4
        catkin_x = int(bx + nx)
        catkin_y = int(by + ny)
        draw.ellipse([catkin_x - 2, catkin_y - 3, catkin_x + 2, catkin_y + 3], fill=CATKIN_MID)
        draw.ellipse([catkin_x - 1, catkin_y - 2, catkin_x + 1, catkin_y + 2], fill=CATKIN_LIGHT)


def draw_splash_burst(draw: ImageDraw.Draw, cx: int, cy: int, age: float):
    """Draw an impact splash — ring of droplets expanding outward."""
    if age > 5:
        return
    fade = max(0.0, 1.0 - age / 5.0)
    num = 10
    for i in range(num):
        angle = i / num * 2 * math.pi + age * 0.3
        dist = age * 4 + 2
        px = int(cx + math.cos(angle) * dist)
        py = int(cy + math.sin(angle) * dist * 0.6)  # slightly oval
        if 0 <= px < S and 0 <= py < S:
            color = WATER_COLORS[i % len(WATER_COLORS)]
            r = int(color[0] * fade)
            g = int(color[1] * fade)
            b = int(color[2] * fade)
            dr = 2 if age < 2 else 1
            draw.ellipse([px - dr, py - dr, px + dr, py + dr], fill=(r, g, b))
    # Central blob for fresh splashes
    if age < 1.5:
        br = int(4 - age * 2)
        a = int(220 * fade)
        draw.ellipse([cx - br, cy - br, cx + br, cy + br], fill=(30, int(160 * fade), a))


def make_frames(num_frames: int = 12) -> list[Image.Image]:
    # Splash positions: (x, y, start_frame)
    splashes = [
        (32, 55, 0), (45, 48, 2), (25, 50, 4), (50, 58, 6),
        (15, 56, 1), (38, 52, 3), (55, 55, 5), (20, 45, 7),
        (42, 60, 8), (30, 42, 9), (10, 50, 10), (58, 45, 11),
    ]

    frames = []
    for f in range(num_frames):
        random.seed(42 + f)
        img = Image.new("RGB", (S, S), BG)
        draw = ImageDraw.Draw(img)

        t = f / num_frames * 2 * math.pi

        # --- Person on the left: pouring water from bucket ---
        pour_cycle = (f / num_frames * 2 * math.pi)
        tilt = 0.4 + 0.5 * (math.sin(pour_cycle) * 0.5 + 0.5)  # tilting bucket
        # Right arm raised holding bucket
        r_arm = 1.0 + 0.3 * math.sin(pour_cycle)
        left_hand, right_hand, _ = draw_stick_person(
            draw, cx=16, foot_y=S - 3, shirt_color=SHIRT_BLUE,
            arm_angle_l=0.4, arm_angle_r=r_arm,
        )
        # Bucket at right hand
        spout_x, spout_y = draw_bucket_pour(draw, right_hand[0], right_hand[1], tilt, f / num_frames)
        # Water stream from bucket
        draw_water_stream(draw, spout_x, spout_y, tilt, num_frames)

        # --- Person on the right: swinging pussy willow ---
        swing = -0.8 + math.sin(t * 2) * 0.9  # swinging motion
        l_arm = 1.2 + 0.4 * math.sin(t * 2)
        left_hand2, right_hand2, _ = draw_stick_person(
            draw, cx=50, foot_y=S - 3, shirt_color=SHIRT_RED,
            arm_angle_l=l_arm, arm_angle_r=0.3,
        )
        # Pussy willow in left hand
        draw_pussy_willow_branch(draw, left_hand2[0], left_hand2[1], swing)

        # --- Splashes everywhere ---
        for sx, sy, start in splashes:
            age = (f - start) % num_frames
            if age < 5:
                draw_splash_burst(draw, sx, sy, age)

        # --- Ground water puddle shimmer ---
        for px in range(0, S, 3):
            shimmer = int(20 + 15 * math.sin(px * 0.5 + t))
            py = S - 1
            if 0 <= px < S:
                draw.point((px, py), fill=(10, shimmer, shimmer + 30))
                draw.point((px, py - 1), fill=(5, shimmer // 2, shimmer // 2 + 15))

        frames.append(img)
    return frames


def make_animated_gif(frames: list[Image.Image], duration_ms: int) -> bytes:
    resized = [
        f.convert("RGB").resize((S, S), Image.LANCZOS).quantize(colors=48).convert("RGB")
        for f in frames
    ]
    buf = BytesIO()
    resized[0].save(
        buf, format="GIF", save_all=True,
        append_images=resized[1:], duration=duration_ms, loop=0,
    )
    return buf.getvalue()


async def main():
    print("Generating Śmigus Dyngus — water pouring & pussy willows!")
    frames = make_frames(num_frames=12)
    delay_ms = 180
    gif_data = make_animated_gif(frames, delay_ms)
    num_chunks = (len(gif_data) + CHUNK_SIZE - 1) // CHUNK_SIZE
    print(f"Animated GIF: {len(frames)} frames, {len(gif_data)} bytes, {num_chunks} chunks")

    if num_chunks > 255:
        print(f"ERROR: {num_chunks} chunks exceeds protocol limit of 255.")
        return

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

    print("Done! Wesołego Śmigusa Dyngusa!")


asyncio.run(main())
