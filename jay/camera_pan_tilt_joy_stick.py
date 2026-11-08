#!/usr/bin/env python3
"""
Joystick-controlled camera pan-tilt with photo capture.
SunFounder AI Fusion Lab Kit: Raspberry Pi + Fusion HAT+ + 2x SF006PRO servos.

Conventions (from the verified Camera Pan-Tilt Reference):
  - Pan  = left/right, PWM channel 2
  - Tilt = up/down,    PWM channel 3
  - Tilt: negative angle = UP, positive angle = DOWN
  - Tilt must never exceed +30 (bracket hits the top plate and stalls the servo)
  - angle(0) = straight ahead and level (requires correct horn zeroing)

Before running: insert the battery and power on the HAT (green PWR LED).
Run with: sudo python3 camera_pan_tilt_joystick.py
"""
import os, time
from picamera2 import Picamera2, Preview
from fusion_hat.adc import ADC
from fusion_hat.pin import Pin, Mode, Pull
from fusion_hat.servo import Servo

# Servo channels (confirmed by channel scan)
PAN_CHANNEL, TILT_CHANNEL = 2, 3

# Joystick ADC pins (X/Y axis) and button pin
X_PIN, Y_PIN = "A1", "A0"
BTN_PIN = 17

# Angle limits to protect servos
PAN_MIN, PAN_MAX = -90, 90      # use -30, 30 for cautious testing
TILT_MIN, TILT_MAX = -90, 30    # negative = up, positive = down. NEVER exceed +30.

# Direction flags: set to -1 if an axis feels inverted on the joystick
PAN_DIRECTION = 1
TILT_DIRECTION = 1

# Deadzone ignores small joystick movement
DEADZONE = 15
MOVE_SPEED = 3
LOOP_DELAY = 0.05

# Return camera to center (0, 0) when the script exits
CENTER_ON_EXIT = True

# Photo save directory (works with sudo)
REAL_USER = os.getenv("SUDO_USER") or os.getlogin()
PHOTO_DIR = os.path.join(f"/home/{REAL_USER}", "Pictures", "camera_pan_tilt")
os.makedirs(PHOTO_DIR, exist_ok=True)

# Initialize servos
pan_servo = Servo(PAN_CHANNEL)
tilt_servo = Servo(TILT_CHANNEL)

# Initialize joystick and button (active-low)
x_adc = ADC(X_PIN)
y_adc = ADC(Y_PIN)
joystick_button = Pin(BTN_PIN, mode=Mode.IN, pull=Pull.UP)  # pressed -> 0

# Initialize camera
camera = Picamera2()
camera.configure(camera.create_preview_configuration(main={"size": (1280, 720)}))

preview_started = False
photo_count = 1
current_pan = 0
current_tilt = 0
last_button_state = 1  # Used for edge detection


def clamp(v, vmin, vmax):
    # Limit value to a safe range
    return max(vmin, min(vmax, v))


def map_value(value, in_min, in_max, out_min, out_max):
    # Map ADC value to a new range
    return (value - in_min) * (out_max - out_min) / (in_max - in_min) + out_min


def apply_deadzone(v, dz):
    # Ignore small joystick movement
    return 0 if (-dz < v < dz) else v


def read_joystick():
    # Read joystick X/Y position, mapped to -100..100
    x = map_value(x_adc.read(), 0, 4095, -100, 100)
    y = map_value(y_adc.read(), 0, 4095, -100, 100)
    return x, y


def step_for(value):
    # Convert a deadzoned joystick value into a fixed angle step
    if value > 0:
        return MOVE_SPEED
    if value < 0:
        return -MOVE_SPEED
    return 0


def set_pan(angle):
    global current_pan
    current_pan = clamp(angle, PAN_MIN, PAN_MAX)
    pan_servo.angle(current_pan)


def set_tilt(angle):
    # Clamp is the safety guard: tilt can never go past +30 (down)
    global current_tilt
    current_tilt = clamp(angle, TILT_MIN, TILT_MAX)
    tilt_servo.angle(current_tilt)


def check_button_press():
    # Detect button press (HIGH -> LOW)
    global last_button_state
    current_state = joystick_button.value()
    pressed = last_button_state == 1 and current_state == 0
    last_button_state = current_state
    return pressed


def next_photo_number():
    # Continue numbering after existing photos so nothing gets overwritten
    n = 1
    while os.path.exists(os.path.join(PHOTO_DIR, f"photo_{n:03d}.jpg")):
        n += 1
    return n


def take_photo():
    # Capture and save one photo
    global photo_count
    filename = f"photo_{photo_count:03d}.jpg"
    filepath = os.path.join(PHOTO_DIR, filename)
    camera.capture_file(filepath)
    print(f"Saved: {filepath}  (pan={current_pan}, tilt={current_tilt})")
    photo_count += 1


def start_preview_if_available():
    # Start camera preview only if a display is available
    global preview_started
    preview_started = False
    if os.getenv("DISPLAY"):
        try:
            camera.start_preview(Preview.QT)
            preview_started = True
        except Exception:
            preview_started = False


def cleanup():
    # Re-center servos, then safely stop camera and release resources.
    # Note: the HAT keeps sending the last PWM signal, so the servos stay
    # stiff after exit. Power off the HAT to release them.
    if CENTER_ON_EXIT:
        try:
            set_pan(0)
            set_tilt(0)
            time.sleep(0.3)
        except Exception:
            pass
    try:
        camera.stop()
    except Exception:
        pass
    if preview_started:
        try:
            camera.stop_preview()
        except Exception:
            pass
    try:
        camera.close()
    except Exception:
        pass


def main():
    global photo_count

    photo_count = next_photo_number()
    start_preview_if_available()
    camera.start()

    # Center camera at startup (straight ahead and level)
    set_pan(0)
    set_tilt(0)

    print("Pan-tilt ready. Move joystick to aim, press button to take a photo, Ctrl+C to quit.")
    print(f"Limits: pan {PAN_MIN}..{PAN_MAX}, tilt {TILT_MIN} (up)..{TILT_MAX} (down)")

    try:
        while True:
            # Read joystick and move camera
            x, y = read_joystick()
            x = apply_deadzone(x, DEADZONE)
            y = apply_deadzone(y, DEADZONE)

            new_pan = clamp(current_pan + PAN_DIRECTION * step_for(x), PAN_MIN, PAN_MAX)
            new_tilt = clamp(current_tilt + TILT_DIRECTION * step_for(y), TILT_MIN, TILT_MAX)

            if new_pan != current_pan:
                set_pan(new_pan)

            if new_tilt != current_tilt:
                set_tilt(new_tilt)

            # Take photo when button is pressed
            if check_button_press():
                take_photo()

            time.sleep(LOOP_DELAY)

    except KeyboardInterrupt:
        print("\nExiting...")
    finally:
        cleanup()


if __name__ == "__main__":
    main()

