# Camera Pan-Tilt Reference (SunFounder AI Fusion Lab Kit)

Confirmed configuration for the camera pan-tilt on a Raspberry Pi with the SunFounder Fusion HAT+. Verified by hands-on testing.

## Hardware

- **Board:** Raspberry Pi + SunFounder Fusion HAT+
- **Servos:** 2 × digital servo (SF006PRO), driven by the Fusion HAT+ PWM ports
- **Camera:** Raspberry Pi camera module (via `picamera2`)
- **Library:** `fusion_hat` (`from fusion_hat.servo import Servo`)
- **Power:** The battery must be inserted and the HAT powered on (power button). Servos do not move without it.

## Servo channels

| Axis | Motion | Fusion HAT PWM channel |
|------|--------|------------------------|
| Pan  | Left / right (turn) | **2** |
| Tilt | Up / down (nod)     | **3** |

```python
PAN_CHANNEL, TILT_CHANNEL = 2, 3
```

## Angle conventions and limits

| Axis | Negative angle | Positive angle | Safe range |
|------|----------------|----------------|------------|
| Pan  | One side (left/right) | Other side | `-90` to `90` (testing used `-30` to `30`) |
| Tilt | **Up**          | **Down**        | **`-90` (max up) to `30` (max down)** |

```python
PAN_MIN, PAN_MAX = -90, 90     # use -30, 30 for cautious testing
TILT_UP, TILT_DOWN = -90, 30   # negative = up, positive = down
```

- `angle(0)` = centered position (camera facing straight ahead and level, after correct zeroing).
- Going beyond `+30` on tilt drives the bracket into the top plate and stalls the servo. Don't exceed it.

## Servo zeroing (Zero button)

- **What it does:** Pressing the **Zero** button **twice quickly** sets all PWM outputs to a 1500 µs pulse / 20000 µs period, which is servo center (0°). The white LED flashes to confirm.
- **What it does NOT do:** It stores no configuration and changes no settings. It's only an aid for assembly.
- **Why it matters:** The servo horn and bracket must be attached while the servo is at 0°, so that `angle(0)` in code points the camera straight ahead. If the horn is mounted off-center, commanded angles push the bracket into its end stop.

### Re-zeroing procedure

1. Power on the Fusion HAT+.
2. Press **Zero** twice quickly. The white LED flashes and the servos move to 0°.
3. With power still on, remove the screw from the servo horn.
4. Pull the bracket and horn off the shaft, then re-seat them so the camera faces **straight forward and level**.
5. Put the screw back in and power-cycle the HAT.
6. Verify with `tilt_manual.py` (type angles such as `0`, `-30`, `30`).

## Troubleshooting findings

| Symptom | Cause | Fix |
|---------|-------|-----|
| Pan worked, tilt didn't respond as expected | Channel numbers in code didn't match the physical plugs | Use `PAN=2`, `TILT=3` (confirmed by channel scan) |
| Tilt always went fully down regardless of angle | Horn/bracket mounted off-center, so the servo stalled against the plate | Re-zero and re-seat the horn (see above) |
| Servo locked stiff after the script ended; couldn't move it by hand | Normal: the HAT keeps sending the last PWM signal, so the servo holds position | Power off to release. If it's hot, it's stalled against something; fix the mounting. |
| Confusion about "tilt" | Terminology | **Pan = left/right**, **Tilt = up/down** |

## Diagnostic checklist (if a servo stops working)

1. Battery inserted and charged; HAT powered on (green PWR LED).
2. Plug orientation: **orange/yellow = S (signal)**, **red = +**, **brown/black = − (GND)**.
3. Run a channel scan to find which port actually drives which servo.
4. Swap test: move the suspect servo to a known-good port.
   - Moves → the original port or plug is the problem.
   - Doesn't move → the servo or cable is the problem.
5. Mechanical check: remove the horn screw and test the bare servo.
   - Shaft turns → the bracket is binding or the horn is misaligned.
   - Hums only → jammed or stripped gears.
   - Silent → dead servo or broken cable.

## Test scripts

| Script | Purpose |
|--------|---------|
| `camera_pan_tilt_test.py` | Sweeps pan, then tilt, in 10° steps, printing each angle |
| `tilt_manual.py` | Type an angle to move only the tilt servo |
| `servo_channel_check.py` | Wiggles each channel 0–11 to identify which port drives which servo |
| `tilt_troubleshoot.py` | Interactive channel scan with y/n prompts and hardware-check guidance |

Run all scripts with `sudo python3 <script>.py`.

## Constants for the joystick control script

```python
PAN_CHANNEL, TILT_CHANNEL = 2, 3
PAN_MIN, PAN_MAX = -90, 90
TILT_MIN, TILT_MAX = -90, 30   # negative = up, positive = down
```

If joystick up/down feels inverted, flip the sign of the tilt step in the main loop.

