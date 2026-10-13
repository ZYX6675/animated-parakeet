"""Fake renderer for tests: fake_render.py INPUT OUTDIR [mode].
The picture is derived from the file's bytes, so identical files give identical pictures.
Modes: same | small_noise (below tolerance) | big_noise (visible change) | two_pages
"""
import hashlib
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from parity.png import write_png  # noqa: E402

src, outdir = sys.argv[1], sys.argv[2]
mode = sys.argv[3] if len(sys.argv) > 3 else "same"
W, H = 40, 30
with open(src, "rb") as fh:
    seed = hashlib.sha256(fh.read()).digest()
pages = 2 if mode == "two_pages" else 1
for n in range(1, pages + 1):
    px = bytearray(W * H * 3)
    for i in range(len(px)):
        px[i] = seed[(i + n) % len(seed)]
    if mode == "small_noise":
        for i in range(0, 30, 3):
            px[i] = min(255, px[i] + 5)
    if mode == "big_noise":
        for i in range(0, len(px) // 4, 3):
            px[i] = 255 - px[i]
    write_png(os.path.join(outdir, f"page-{n}.png"), W, H, bytes(px))
