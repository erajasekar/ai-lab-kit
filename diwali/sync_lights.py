# Light the ring in sync with any WAV file (thin wrapper around diwali_show.py).
#   python3 sync_lights.py audio/fire-cracker-sound.wav --style rangoli
# Convert mp3 -> wav first on a computer (the Pi does not need ffmpeg):
#   ffmpeg -i song.mp3 -ac 2 -ar 44100 -c:a pcm_s16le audio/song.wav
import argparse
import diwali_show as d

ap = argparse.ArgumentParser()
ap.add_argument("file")
ap.add_argument("--style", choices=list(d.STYLES), default="fireworks")
ap.add_argument("--brightness", type=float, default=0.5)
ap.add_argument("--latency", type=float, default=0.0)
ap.add_argument("--device")
ap.add_argument("--sim", action="store_true")
ap.add_argument("--no-audio", action="store_true")
a = ap.parse_args()
d.run_file(a.file, a.style, a)
