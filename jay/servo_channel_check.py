#!/usr/bin/env python3
"""
Servo channel check.
Step 1: wiggles channel 3 (the tilt channel) on its own.
Step 2: wiggles every channel 0-11 one at a time so you can see
        which port the tilt servo is actually plugged into.

Usage: sudo python3 servo_channel_check.py
"""
import time
from fusion_hat.servo import Servo


def wiggle(channel, angle=30, times=2):
    s = Servo(channel)
    for _ in range(times):
        s.angle(angle)
        time.sleep(0.5)
        s.angle(-angle)
        time.sleep(0.5)
    s.angle(0)
    time.sleep(0.3)


print("Step 1: wiggling channel 3 (tilt) only...")
wiggle(3)
input("Did the tilt servo move? Press Enter to scan all channels...")

print("Step 2: scanning channels 0-11. Watch which servo moves.")
for ch in range(12):
    print(f"  channel {ch}")
    try:
        wiggle(ch, times=1)
    except Exception as e:
        print(f"    error: {e}")
print("Done.")

