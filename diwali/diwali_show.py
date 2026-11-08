# ====================================================================
# Diwali light & music show for Raspberry Pi + SunFounder Fusion HAT
#
# Three options (pick one):
#   1  Diya Glow       - gentle "Happy Diwali" tune, warm diya lamps on the ring
#   2  Patakha Fireworks - dhol beat + rockets and bursts
#   3  Rangoli Colours - Bhupali-style tune, symmetric colour patterns
#
# How sync works: each option is written ONCE as a "score". Every note or
# drum hit in the score becomes both an audio sample and an LED event with
# the same timestamp. The WAV is rendered from the score, the LED loop runs
# from the same clock, so they cannot drift apart. If your speaker starts a
# bit late/early, nudge it with --latency (seconds, e.g. 0.15).
#
# Usage:
#   python3 diwali_show.py            # shows a menu
#   python3 diwali_show.py 2          # play option 2
#   python3 diwali_show.py 1 --brightness 0.4 --latency 0.1
#   python3 diwali_show.py 3 --sim    # no hardware: draw the ring in terminal
#
# The melodies are original tunes composed for this show (not a recording
# of any specific copyrighted song). Edit the note lists to swap in your own.
# ====================================================================

import argparse
import colorsys
import math
import os
import random
import shutil
import struct
import subprocess
import sys
import time
import wave

LED_COUNT = 12
SR = 44100  # CD rate: avoids ALSA resampling artifacts on the Pi
HERE = os.path.dirname(os.path.abspath(__file__))

# ---------------------------------------------------------------- notes
_PC = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}


def midi(name):
    pc = _PC[name[0]]
    i = 1
    if name[i] == "#":
        pc += 1
        i += 1
    elif name[i] == "b":
        pc -= 1
        i += 1
    return 12 * (int(name[i:]) + 1) + pc


def freq(m):
    return 440.0 * 2 ** ((m - 69) / 12)


# ---------------------------------------------------------------- score
class Score:
    """Single source of truth: every call adds audio AND an LED event."""

    def __init__(self, bpm):
        self.beat = 60.0 / bpm
        self.audio = []   # (kind, start, dur, f0, f1, amp)
        self.events = []  # (time, name, data)
        self.end = 0.0

    def b(self, beats):
        return beats * self.beat

    def _end(self, t):
        self.end = max(self.end, t)

    def note(self, t, beats, name, amp=0.5, kind="pluck", led=True):
        m = midi(name)
        d = self.b(beats)
        self.audio.append((kind, t, d, freq(m), 0, amp))
        if led:
            self.events.append((t, "note", m))
        self._end(t + d)

    def hit(self, t, kind, amp=0.6, led=True, data=None):
        """Percussion / effect: kind in dhol, tilli, boom, bell."""
        self.audio.append((kind, t, 0.0, 0, 0, amp))
        if led:
            self.events.append((t, kind, data))
        self._end(t + 0.5)

    def whistle(self, t, dur, f0=500, f1=2200, amp=0.25, data=None):
        self.audio.append(("whistle", t, dur, f0, f1, amp))
        self.events.append((t, "rocket", dur))
        self._end(t + dur)

    def drone(self, t, beats, amp=0.18):
        for n in ("C4", "G4"):
            self.audio.append(("drone", t, self.b(beats), freq(midi(n)), 0, amp))

    def mark(self, t, name, data=None):
        self.events.append((t, name, data))
        self._end(t)

    def seq(self, t, items, **kw):
        """items: (note_name | None, beats). Returns time after the phrase."""
        for name, beats in items:
            if name:
                self.note(t, beats, name, **kw)
            t += self.b(beats)
        return t


# ---------------------------------------------------------------- synth
def render_wav(score, path):
    n = int((score.end + 2.0) * SR)
    buf = [0.0] * n
    rng = random.Random(7)
    tp = 2 * math.pi

    def mix(i0, vals):
        for k, v in enumerate(vals):
            j = i0 + k
            if j >= n:
                break
            buf[j] += v

    for kind, t, d, f0, f1, amp in score.audio:
        i0 = int(t * SR)
        if kind in ("pluck", "drone"):
            tau = d * 0.6 + 0.12 if kind == "pluck" else d * 0.9
            L = int(min(tau * 4, d + 0.6) * SR)
            w = tp * f0 / SR
            atk = 0.006 * SR
            mix(i0, [
                amp * min(1.0, k / atk) * math.exp(-k / SR / tau)
                * (math.sin(w * k) + 0.45 * math.sin(2 * w * k)
                   + 0.2 * math.sin(3 * w * k) + 0.08 * math.sin(5 * w * k))
                for k in range(L)])
        elif kind == "bell":
            L = int(2.2 * SR)
            parts = [(1.0, 1.0), (2.76, 0.6), (5.4, 0.35), (8.93, 0.2)]
            base = 1046.5
            mix(i0, [
                amp * 0.5 * sum(a * math.exp(-k / SR / (1.2 / (1 + 0.6 * r)))
                                * math.sin(tp * base * r * k / SR)
                                for r, a in parts)
                for k in range(L)])
        elif kind == "dhol":
            L = int(0.35 * SR)
            ph = 0.0
            out = []
            for k in range(L):
                tt = k / SR
                f = 55 + 90 * math.exp(-tt * 18)
                ph += tp * f / SR
                out.append(amp * 1.0 * math.exp(-tt * 9) * (math.sin(ph) + 0.6 * math.sin(2 * ph) + 0.4 * math.sin(3 * ph))
                           + amp * 0.3 * math.exp(-tt * 60) * rng.uniform(-1, 1))
            mix(i0, out)
        elif kind == "tilli":
            L = int(0.12 * SR)
            prev = 0.0
            out = []
            for k in range(L):
                x = rng.uniform(-1, 1)
                out.append(amp * 0.8 * math.exp(-k / SR * 45) * (x - prev))
                prev = x
            mix(i0, out)
        elif kind == "boom":
            L = int(1.1 * SR)
            ph = 0.0
            out = []
            lp = 0.0
            for k in range(L):
                tt = k / SR
                ph += tp * (70 + 90 * math.exp(-tt * 8)) / SR
                lp += 0.08 * (rng.uniform(-1, 1) - lp)
                crackle = (rng.uniform(-1, 1) * 0.5
                           if rng.random() < 0.02 * math.exp(-tt * 2) else 0)
                out.append(amp * (1.0 * math.exp(-tt * 4) * (math.sin(ph) + 0.5 * math.sin(2 * ph))
                                  + 2.0 * math.exp(-tt * 6) * lp
                                  + math.exp(-tt * 3) * crackle))
            mix(i0, out)
        elif kind == "whistle":
            L = int(d * SR)
            ph = 0.0
            out = []
            for k in range(L):
                x = k / max(L - 1, 1)
                ph += tp * (f0 + (f1 - f0) * x * x) / SR
                out.append(amp * math.sin(ph) * min(1, k / 400) * (1 - 0.5 * x))
            mix(i0, out)

    peak = max(max(buf), -min(buf), 1e-9)
    scale = 0.6 * 32767 / peak  # headroom: small amps clip/distort easily
    with wave.open(path, "wb") as wf:
        wf.setnchannels(2)
        wf.setsampwidth(2)
        wf.setframerate(SR)
        wf.writeframes(b"".join(
            struct.pack("<hh", int(v * scale), int(v * scale)) for v in buf))


# ---------------------------------------------------------------- LED engine
def clamp(v):
    return 0.0 if v < 0 else 255.0 if v > 255 else v


def hsv(h, s=1.0, v=1.0):
    r, g, b = colorsys.hsv_to_rgb(h % 1.0, s, v)
    return (r * 255, g * 255, b * 255)


class Ring:
    """Float RGB buffer with exponential decay (half-life in seconds)."""

    def __init__(self, half_life):
        self.px = [[0.0, 0.0, 0.0] for _ in range(LED_COUNT)]
        self.half = half_life

    def add(self, i, rgb, k=1.0):
        p = self.px[i % LED_COUNT]
        for c in range(3):
            p[c] = min(255.0, p[c] + rgb[c] * k)

    def setv(self, i, rgb, k=1.0):
        self.px[i % LED_COUNT] = [rgb[0] * k, rgb[1] * k, rgb[2] * k]

    def fill(self, rgb, k=1.0):
        for i in range(LED_COUNT):
            self.setv(i, rgb, k)

    def decay(self, dt):
        f = 0.5 ** (dt / self.half)
        for p in self.px:
            p[0] *= f
            p[1] *= f
            p[2] *= f


# ---- Option 1: Diya Glow ------------------------------------------------
def build_diya():
    s = Score(bpm=96)
    A = [("E4", .5), ("G4", .5), ("A4", 1), ("G4", 1), ("E4", 1),
         ("D4", .5), ("E4", .5), ("G4", 1), ("E4", 2)]
    B = [("A4", .5), ("C5", .5), ("D5", 1), ("C5", 1), ("A4", 1),
         ("G4", .5), ("A4", .5), ("C5", 1), ("A4", 2)]
    C = [("E5", 1), ("D5", .5), ("C5", .5), ("A4", 1), ("G4", 1),
         ("E4", .5), ("D4", .5), ("C4", 3)]
    t = s.b(2)
    s.hit(0.0, "bell", 0.6)
    for ph in (A, A, B, C):
        s.hit(t, "bell", 0.35)
        for k in range(0, 8, 2):
            s.drone(t + s.b(k), 2)
        s.mark(t, "bar")
        t = s.seq(t, ph, amp=0.5)
    s.hit(t, "bell", 0.7)
    s.mark(t, "finale")
    s.end = t + 3.5
    return s


def led_diya():
    ring = Ring(half_life=0.55)
    st = {"fin": None, "pulse": 0.0}

    def on_event(t, name, data):
        if name == "note":
            pc = data % 12
            warm = min(1.0, max(0.0, (data - 60) / 24))   # higher = more golden
            col = (255, 90 + 120 * warm, 5 + 40 * warm)
            ring.add(pc, col, 1.0)
            ring.add(pc - 1, col, 0.25)
            ring.add(pc + 1, col, 0.25)
        elif name == "bell":
            ring.fill((255, 170, 30), 0.35)
        elif name == "bar":
            st["pulse"] = 0.12
        elif name == "finale":
            st["fin"] = t

    def ambient(t, dt):
        if st["pulse"] > 0:
            for i in range(LED_COUNT):
                ring.add(i, (255, 120, 10), st["pulse"] * 0.25)
        if st["fin"] is not None:
            k = min(1.0, (t - st["fin"]) / 1.2)
            fade = max(0.0, 1 - max(0.0, t - st["fin"] - 2.3) / 1.2)
            for i in range(LED_COUNT):
                fl = random.uniform(0.6, 1.0)
                ring.setv(i, (255, 110 + 50 * fl, 10), k * fade * fl)

    def post(px):  # diya flicker
        return [[c * random.uniform(0.88, 1.0) for c in p] for p in px]

    return ring, on_event, ambient, post


# ---- Option 2: Patakha Fireworks ----------------------------------------
def build_fireworks():
    s = Score(bpm=132)
    bar = s.b(4)
    riff1 = [("E5", .5), ("G5", .5), ("A5", 1), ("G5", .5), ("E5", .5), ("D5", 1)]
    riff2 = [("C5", .5), ("D5", .5), ("E5", 1), ("D5", 1), ("C5", 1)]
    nbars = 12
    for i in range(nbars):
        t = i * bar
        # dhol pattern
        s.hit(t, "dhol", 0.7, data=i)
        s.hit(t + s.b(1.5), "tilli", 0.5)
        s.hit(t + s.b(2), "dhol", 0.6, led=False)
        s.hit(t + s.b(3), "tilli", 0.5)
        s.hit(t + s.b(3.5), "tilli", 0.4)
        if i >= 2 and i < nbars - 1:
            s.seq(t, riff1 if i % 2 == 0 else riff2, amp=0.35)
        # rocket in the last beat of odd bars, boom lands on next bar's beat 1
        if i % 2 == 0 and 0 < i < nbars - 1:
            pass
        if i % 2 == 1 and i < nbars - 2:
            s.whistle(t + s.b(3), s.b(1), amp=0.2)
            s.hit(t + bar, "boom", 0.7, data=i)
    # finale: rapid triple boom
    tf = (nbars - 1) * bar
    for k in range(4):
        s.hit(tf + k * s.b(0.5), "boom", 0.6, data=100 + k)
    s.hit(tf, "bell", 0.5)
    s.mark(tf, "finale")
    s.end = tf + 3.0
    return s


def led_fireworks():
    ring = Ring(half_life=0.22)
    st = {"rocket": None, "fin": None, "ci": 0}
    rng = random.Random(3)
    cols = [(255, 40, 0), (255, 200, 0), (255, 0, 140), (0, 220, 80),
            (60, 100, 255), (255, 255, 255)]

    def on_event(t, name, data):
        if name == "rocket":
            st["rocket"] = (t, data)
        elif name == "boom":
            c = cols[st["ci"] % len(cols)]
            st["ci"] += 1
            st["rocket"] = None
            ring.fill(c, 0.9)
        elif name == "tilli":
            ring.add(rng.randrange(LED_COUNT), rng.choice(cols), 0.9)
        elif name == "dhol":
            ring.add(0, (255, 120, 0), 0.8)
            ring.add(6, (255, 120, 0), 0.8)
        elif name == "note":
            ring.add(data % 12, (255, 190, 40), 0.35)
        elif name == "finale":
            st["fin"] = t

    def ambient(t, dt):
        r = st["rocket"]
        if r:
            x = (t - r[0]) / r[1]
            if 0 <= x <= 1:
                pos = int(x * x * 30) % LED_COUNT        # speeds up
                ring.setv(pos, (255, 230, 140), 1.0)
        if st["fin"] is not None and t > st["fin"] + 2.2:
            ring.fill(hsv(t * 0.8), 0.6 * max(0, 1 - (t - st["fin"] - 2.2) / 0.8))

    return ring, on_event, ambient, None


# ---- Option 3: Rangoli Colours ------------------------------------------
def build_rangoli():
    s = Score(bpm=108)
    m1a = [("E4", 1), ("G4", 1), ("A4", 1), ("G4", 1)]
    m1b = [("E4", .5), ("D4", .5), ("C4", 1), ("D4", 1), ("E4", 1)]
    m2a = [("A4", 1), ("C5", 1), ("D5", 1), ("C5", 1)]
    m2b = [("A4", .5), ("G4", .5), ("E4", 1), ("G4", 1), ("A4", 1)]
    m3a = [("C5", 1), ("D5", 1), ("E5", 1), ("G5", 1)]
    m3b = [("E5", 1), ("D5", 1), ("C5", 2)]
    end = [("A4", 1), ("G4", 1), ("E4", 1), ("C4", 1)]
    song = [m1a, m1b, m2a, m2b, m3a, m3b, end]
    t = 0.0
    s.hit(0, "bell", 0.5)
    for rep in range(2):
        for bi, ph in enumerate(song):
            for k in range(2):
                s.hit(t + s.b(2 * k), "dhol", 0.5, data=bi)
            s.hit(t + s.b(1), "tilli", 0.35)
            s.hit(t + s.b(3), "tilli", 0.35)
            if rep == 1:
                s.hit(t + s.b(1.5), "tilli", 0.25, led=False)
                s.hit(t + s.b(3.5), "tilli", 0.25, led=False)
            s.drone(t, 4, amp=0.14)
            s.mark(t, "bar", bi)
            t = s.seq(t, ph, amp=0.45)
    s.hit(t, "bell", 0.7)
    s.mark(t, "finale")
    s.end = t + 4.0
    return s


def led_rangoli():
    ring = Ring(half_life=0.45)
    pal = {0: (255, 100, 0), 2: (255, 0, 120), 4: (255, 190, 0),
           7: (0, 200, 60), 9: (90, 60, 255)}
    st = {"hue": 0.0, "fin": None, "bar": (255, 100, 0)}

    def on_event(t, name, data):
        if name == "note":
            pc = data % 12
            col = pal.get(pc, (255, 255, 255))
            k = 1.0 if data >= 67 else 0.8
            for off in (0, 6):                       # mirror = rangoli symmetry
                ring.add(pc + off, col, k)
                ring.add(pc + off - 1, col, 0.3)
                ring.add(pc + off + 1, col, 0.3)
        elif name == "bar":
            st["hue"] += 0.09
        elif name == "dhol":
            ring.fill(hsv(st["hue"]), 0.18)
        elif name == "bell":
            ring.fill((255, 200, 60), 0.5)
        elif name == "finale":
            st["fin"] = t

    def ambient(t, dt):
        if st["fin"] is not None:
            x = t - st["fin"]
            fade = max(0.0, 1 - max(0.0, x - 2.8) / 1.2)
            for i in range(LED_COUNT):
                ring.setv(i, hsv(i / LED_COUNT + x * 0.5), fade)

    return ring, on_event, ambient, None


# ---- Option 4: sync to an audio file (WAV) -------------------------------
# Works on any 16-bit PCM WAV. Convert mp3 -> wav once on a computer:
#   ffmpeg -i song.mp3 -ac 2 -ar 44100 -c:a pcm_s16le audio/song.wav
import array

HOP_SEC = 0.01     # analysis frame = 10 ms
AUDIO_DIR = os.path.join(HERE, "audio")


def analyse_wav(path):
    """Return (onsets, envelope, seconds). onsets = [(t, strength 0-1, treble 0-1)]."""
    with wave.open(path) as w:
        nch, rate, raw = w.getnchannels(), w.getframerate(), w.readframes(w.getnframes())
    x = array.array("h")
    x.frombytes(raw)
    if nch == 2:                                   # stereo -> mono
        x = array.array("h", [(a + b) >> 1 for a, b in zip(x[0::2], x[1::2])])
    step = max(1, round(rate / 22050))             # decimate to ~22 kHz
    x = x[::step]
    arate = rate / step
    hop = max(1, int(arate * HOP_SEC))
    fps = arate / hop

    a, lp = 0.11, 0.0                              # one-pole low-pass (~400 Hz)
    low_e, high_e = [], []
    for f in range(len(x) // hop):
        sl = sh = 0.0
        for v in x[f * hop:(f + 1) * hop]:
            lp += a * (v - lp)
            h = v - lp
            sl += lp * lp
            sh += h * h
        low_e.append(math.sqrt(sl / hop))
        high_e.append(math.sqrt(sh / hop))
    energy = [l + h for l, h in zip(low_e, high_e)]
    peak = max(energy) or 1.0
    energy = [e / peak for e in energy]

    onsets, last, win = [], -1e9, int(0.4 * fps)
    for i in range(2, len(energy)):
        recent = energy[max(0, i - win):i]
        avg = sum(recent) / len(recent)
        rise = energy[i] - max(avg, energy[i - 1])
        if rise > 0.06 and energy[i] >= energy[i - 1] and i - last > 0.07 * fps:
            j = max(range(i, min(i + 4, len(energy))), key=lambda k: energy[k])
            hi = high_e[j] / ((low_e[j] + high_e[j]) or 1)
            onsets.append((i / fps, min(1.0, rise * 1.1 + 0.2 * energy[j]), hi))
            last = i
    env, sm = [], 0.0
    for e in energy:
        sm += 0.15 * (e - sm)
        env.append(sm)
    return onsets, env, len(x) / arate, fps


_COLS = [(255, 40, 0), (255, 190, 0), (255, 0, 140), (0, 220, 80),
         (60, 100, 255), (255, 255, 255)]


def style_fireworks():
    ring = Ring(0.2)
    st = {"i": 0}

    def on_onset(t, s, hi):
        if s > 0.55:                      # big bang: whole ring bursts
            ring.fill(_COLS[st["i"] % len(_COLS)], 0.55 + 0.45 * s)
            st["i"] += 1
        else:                             # crackle: random sparks
            for _ in range(1 + int(s * 4)):
                ring.add(random.randrange(LED_COUNT), random.choice(_COLS), 0.6 + 0.4 * s)

    def ambient(t, e):
        ring.add(int(t * 9) % LED_COUNT, (255, 90, 0), 0.05 + 0.25 * e)
    return ring, on_onset, ambient


def style_diya():
    ring = Ring(0.4)

    def on_onset(t, s, hi):
        for i in range(LED_COUNT):
            ring.add(i, (255, 120 + 80 * hi, 10), 0.3 + 0.6 * s)

    def ambient(t, e):
        for i in range(LED_COUNT):
            ring.add(i, (255, 100, 5), (0.04 + 0.22 * e) * random.uniform(0.6, 1))
    return ring, on_onset, ambient


def style_rangoli():
    ring = Ring(0.3)
    st = {"hue": 0.0}

    def on_onset(t, s, hi):
        st["hue"] += 0.08
        p = random.randrange(LED_COUNT // 2)
        c = hsv(st["hue"] + 0.4 * hi)
        for off in (0, LED_COUNT // 2):
            ring.add(p + off, c, 0.5 + 0.5 * s)
            ring.add(p + off + 1, c, 0.25 * s)
            ring.add(p + off - 1, c, 0.25 * s)

    def ambient(t, e):
        for i in range(LED_COUNT):
            ring.add(i, hsv(i / LED_COUNT + t * 0.1), 0.02 + 0.18 * e)
    return ring, on_onset, ambient


STYLES = {"fireworks": style_fireworks, "diya": style_diya, "rangoli": style_rangoli}


def run_file(wav, style, args):
    """Play a WAV and light the ring from its beats/loudness."""
    print("Analysing %s ..." % os.path.basename(wav))
    onsets, env, dur, fps = analyse_wav(wav)
    print("%.1fs, %d hits detected" % (dur, len(onsets)))
    ring, on_onset, ambient = STYLES[style]()
    strip = open_strip(args.sim)
    proc = None if args.no_audio else start_audio(wav, args.device)
    t0, oi, last = time.monotonic(), 0, 0.0
    try:
        while True:
            t = time.monotonic() - t0 - args.latency
            if t > dur + 0.5:
                break
            while oi < len(onsets) and onsets[oi][0] <= t:
                on_onset(*onsets[oi])
                oi += 1
            ring.decay(max(0.0, t - last))
            last = t
            ambient(t, env[min(max(int(t * fps), 0), len(env) - 1)])
            for i in range(LED_COUNT):
                strip[i] = tuple(int(clamp(c) * args.brightness) for c in ring.px[i])
            strip.show()
            time.sleep(0.02)
    except KeyboardInterrupt:
        pass
    finally:
        if proc and proc.poll() is None:
            proc.terminate()
        strip.fill(0)
        strip.show()
        print("\nShubh Deepavali!")


OPTIONS = {
    "1": ("Diya Glow", build_diya, led_diya),
    "2": ("Patakha Fireworks", build_fireworks, led_fireworks),
    "3": ("Rangoli Colours", build_rangoli, led_rangoli),
    "4": ("Firecracker Sound (audio-synced)", None, None),
    "5": ("Fireworks Diwali Celebration (audio-synced)", None, None),
}

# options that play a WAV from audio/ and light the ring from the sound itself
AUDIO_OPTIONS = {"4": "fire-cracker-sound.wav",
                 "5": "fireworks-diwali-celebration.wav"}


# ---------------------------------------------------------------- hardware
class SimStrip:
    """Terminal stand-in for the NeoPixel ring (for testing without a Pi)."""

    def __init__(self):
        self.px = [(0, 0, 0)] * LED_COUNT

    def __setitem__(self, i, c):
        self.px[i] = c

    def fill(self, c):
        if isinstance(c, int):
            c = (c, c, c)
        self.px = [c] * LED_COUNT

    def show(self):
        s = "".join("\x1b[48;2;%d;%d;%dm  \x1b[0m" % tuple(int(x) for x in p)
                    for p in self.px)
        sys.stdout.write("\r" + s + " ")
        sys.stdout.flush()


def open_strip(sim):
    if sim:
        return SimStrip()
    try:
        import board
        import neopixel_spi as neopixel
        spi = board.SPI()
        return neopixel.NeoPixel_SPI(spi, LED_COUNT, pixel_order=neopixel.GRB,
                                     auto_write=False)
    except Exception as e:
        sys.exit("\n*** NeoPixel ring NOT available: %r\n"
                 "Run this on the Pi (same python that runs python/1.9_NeoPixel.py).\n"
                 "Use --sim to preview in the terminal." % e)


def find_speaker():
    """Pick an ALSA output: USB speaker first, then the Fusion HAT card."""
    try:
        out = subprocess.run(["aplay", "-l"], capture_output=True, text=True).stdout
    except Exception:
        return None
    cards = [l for l in out.splitlines() if l.startswith("card ")]
    for keys in (("usb",), ("voicehat", "googlevoi")):
        for line in cards:
            low = line.lower()
            if any(k in low for k in keys):
                return "plughw:%s,0" % line.split()[1].rstrip(":")
    return None


def start_audio(path, device=None):
    try:  # Fusion HAT speaker amp (name from SunFounder lib; harmless if absent)
        from fusion_hat.device import enable_speaker
        enable_speaker()
    except Exception:
        pass
    device = device or find_speaker()
    if device:
        print("Audio device:", device)
    if device and shutil.which("aplay"):
        return subprocess.Popen(["aplay", "-q", "-D", device, path])
    for cmd in (["aplay", "-q"], ["paplay"], ["afplay"],
                ["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet"]):
        if shutil.which(cmd[0]):
            return subprocess.Popen(cmd + [path])
    print("No audio player found (aplay/paplay/ffplay) - lights only")
    return None


# ---------------------------------------------------------------- main
def run(key, args):
    title, build, leds = OPTIONS[key]
    print("\n=== %s ===" % title)
    if key in AUDIO_OPTIONS:
        run_file(os.path.join(AUDIO_DIR, AUDIO_OPTIONS[key]), args.style, args)
        return
    score = build()
    score.events.sort(key=lambda e: e[0])
    wav = os.path.join(HERE, "diwali_%s.wav" % key)
    if args.regen or not os.path.exists(wav):
        print("Rendering audio (first run only)...")
        render_wav(score, wav)

    ring, on_event, ambient, post = leds()
    strip = open_strip(args.sim)
    events = list(score.events)
    ei = 0
    total = score.end
    proc = None if args.no_audio else start_audio(wav, args.device)
    t0 = time.monotonic()
    last = 0.0
    try:
        while True:
            t = time.monotonic() - t0 - args.latency
            if t > total:
                break
            while ei < len(events) and events[ei][0] <= t:
                on_event(events[ei][0], events[ei][1], events[ei][2])
                ei += 1
            dt = max(0.0, t - last)
            last = t
            ring.decay(dt)
            ambient(t, dt)
            px = post(ring.px) if post else ring.px
            for i in range(LED_COUNT):
                strip[i] = tuple(int(clamp(c) * args.brightness) for c in px[i])
            strip.show()
            time.sleep(0.02)
    except KeyboardInterrupt:
        pass
    finally:
        if proc and proc.poll() is None:
            proc.terminate()
        strip.fill(0)
        strip.show()
        print("\nShubh Deepavali!")


def main():
    ap = argparse.ArgumentParser(description="Diwali lights + music show")
    ap.add_argument("option", nargs="?", choices=list(OPTIONS) + ["all"])
    ap.add_argument("--brightness", type=float, default=0.5)
    ap.add_argument("--latency", type=float, default=0.0,
                    help="seconds to delay LEDs vs audio (negative = earlier)")
    ap.add_argument("--style", choices=["fireworks", "diya", "rangoli"],
                    default="fireworks", help="light style for options 4 and 5")
    ap.add_argument("--regen", action="store_true", help="re-render the WAV")
    ap.add_argument("--sim", action="store_true", help="draw ring in terminal")
    ap.add_argument("--device", help="ALSA device for aplay, e.g. plughw:0,0 "
                    "(list with: aplay -l)")
    ap.add_argument("--no-audio", action="store_true")
    args = ap.parse_args()

    key = args.option
    if not key:
        for k, (name, _, _) in OPTIONS.items():
            print("  %s) %s" % (k, name))
        key = input("Choose 1-5 (or 'all'): ").strip()
    for k in (["1", "2", "3"] if key == "all" else [key]):
        run(k, args)


if __name__ == "__main__":
    main()
