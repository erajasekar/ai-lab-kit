"""Streaming speech-to-text with Vosk, using an external USB mic.

The Fusion HAT's Vosk wrapper records from the default (HAT) mic, so here we
capture audio ourselves with `arecord` from a chosen ALSA device and feed it to
Vosk directly.

Usage:
    python stt_vosk_stream.py                  # auto-detect USB mic
    python stt_vosk_stream.py --list           # show capture devices
    python stt_vosk_stream.py --device plughw:2,0
"""
import argparse
import json
import re
import subprocess
import sys

from vosk import KaldiRecognizer, Model, SetLogLevel

RATE = 16000
CHUNK = 4000  # bytes read per iteration (2000 samples, ~125 ms)


def list_devices():
    out = subprocess.run(["arecord", "-l"], capture_output=True, text=True).stdout
    return out


def find_usb_mic():
    """Return an ALSA plughw:<card>,<dev> for the first USB capture card."""
    for line in list_devices().splitlines():
        m = re.match(r"card (\d+): (\S+) \[(.*?)\], device (\d+):", line)
        if not m:
            continue
        card, short, long_name, dev = m.groups()
        # Skip the Fusion HAT's own sound card; prefer anything else (USB)
        if "fusion" in (short + long_name).lower() or "hat" in short.lower():
            continue
        return f"plughw:{card},{dev}"
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--device", help="ALSA capture device, e.g. plughw:2,0")
    ap.add_argument("--list", action="store_true", help="list capture devices")
    ap.add_argument("--lang", default="en-us")
    args = ap.parse_args()

    if args.list:
        print(list_devices())
        return

    device = args.device or find_usb_mic()
    if not device:
        sys.exit("No USB mic found. Run with --list, then pass --device plughw:X,0")
    print("Using mic:", device)

    SetLogLevel(-1)
    rec = KaldiRecognizer(Model(lang=args.lang), RATE)
    rec.SetWords(False)

    # plughw lets ALSA convert the mic's native format to 16 kHz mono S16
    proc = subprocess.Popen(
        ["arecord", "-q", "-D", device, "-f", "S16_LE", "-r", str(RATE),
         "-c", "1", "-t", "raw"],
        stdout=subprocess.PIPE,
    )

    try:
        print("Say something")
        while True:
            data = proc.stdout.read(CHUNK)
            if not data:
                sys.exit("arecord stopped - check the device name (--list)")
            if rec.AcceptWaveform(data):
                text = json.loads(rec.Result()).get("text", "")
                print(f"\r\x1b[Kfinal: {text}")
            else:
                partial = json.loads(rec.PartialResult()).get("partial", "")
                print(f"\r\x1b[Kpartial: {partial}", end="", flush=True)

    except KeyboardInterrupt:
        print("\nExiting...")

    finally:
        proc.terminate()


if __name__ == "__main__":
    main()
