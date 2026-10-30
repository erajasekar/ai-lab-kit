#!/usr/bin/env python3
"""
Manual tilt tester: type an angle, the tilt servo moves there.
Use it to check the servo after re-mounting the bracket.

Usage: sudo python3 tilt_manual.py
"""
from fusion_hat.servo import Servo

TILT_CHANNEL = 3
TILT_MIN, TILT_MAX = -90, 90

tilt = Servo(TILT_CHANNEL)
tilt.angle(0)
print(f"Tilt on channel {TILT_CHANNEL} set to 0°.")
print(f"Type an angle ({TILT_MIN} to {TILT_MAX}) and press Enter. Blank line to quit.")

while True:
    text = input("tilt angle> ").strip()
    if not text:
        break
    try:
        angle = int(text)
    except ValueError:
        print("  enter a whole number")
        continue
    angle = max(TILT_MIN, min(TILT_MAX, angle))
    tilt.angle(angle)
    print(f"  tilt -> {angle}°")

tilt.angle(0)
print("Back to 0°. Done.")
