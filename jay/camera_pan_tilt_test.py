#!/usr/bin/env python3
"""
Simple pan/tilt test: moves one servo at a time in small steps
and prints every angle so you can watch what happens.

Usage: sudo python3 camera_pan_tilt_test.py
"""
import time
from fusion_hat.servo import Servo

PAN_CHANNEL, TILT_CHANNEL = 2, 3

PAN_MIN, PAN_MAX = -90, 90
TILT_UP, TILT_DOWN = -90, 30   # negative = up, positive = down

STEP = 10     # degrees per step
DELAY = 0.3   # seconds per step (raise to slow down)

pan = Servo(PAN_CHANNEL)
tilt = Servo(TILT_CHANNEL)


def sweep(servo, name, start, end):
    step = STEP if end > start else -STEP
    for angle in range(start, end + step, step):
        angle = max(min(angle, max(start, end)), min(start, end))
        print(f"{name:<5} -> {angle:>4}°")
        servo.angle(angle)
        time.sleep(DELAY)


try:
    print("Centering...")
    pan.angle(0)
    tilt.angle(0)
    time.sleep(1)

    print("\n== PAN (left/right), channel", PAN_CHANNEL, "==")
    sweep(pan, "pan", 0, PAN_MIN)
    sweep(pan, "pan", PAN_MIN, PAN_MAX)
    sweep(pan, "pan", PAN_MAX, 0)

    print("\n== TILT (up/down), channel", TILT_CHANNEL, "==")
    print("  going UP")
    sweep(tilt, "tilt", 0, TILT_UP)
    print("  going DOWN")
    sweep(tilt, "tilt", TILT_UP, TILT_DOWN)
    print("  back to center")
    sweep(tilt, "tilt", TILT_DOWN, 0)

    print("\nDone.")
except KeyboardInterrupt:
    print("\nStopped.")
finally:
    pan.angle(0)
    tilt.angle(0)
