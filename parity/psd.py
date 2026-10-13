"""Header-level summary and comparison for PSD/PSB files. Layer contents are not compared yet."""
from __future__ import annotations

import struct

from .findings import Finding
from .ooxml import Unreadable

MODES = {0: "bitmap", 1: "grayscale", 2: "indexed", 3: "rgb", 4: "cmyk", 7: "multichannel", 8: "duotone", 9: "lab"}


def summarize(path) -> dict:
    try:
        with open(path, "rb") as fh:
            head = fh.read(26)
            if len(head) < 26 or head[:4] != b"8BPS":
                raise Unreadable("not a PSD/PSB file")
            version, = struct.unpack(">H", head[4:6])
            channels, height, width, depth, mode = struct.unpack(">HIIHH", head[12:26])
            if version not in (1, 2):
                raise Unreadable(f"unknown PSD version {version}")
            width_bytes = 4 if version == 1 else 8
            fmt = ">I" if version == 1 else ">Q"

            def read_len(size=4):
                raw = fh.read(size)
                if len(raw) < size:
                    raise Unreadable("truncated file")
                return struct.unpack(">I" if size == 4 else fmt, raw)[0]

            fh.seek(read_len(4), 1)  # color mode data
            fh.seek(read_len(4), 1)  # image resources
            layers = 0
            if read_len(width_bytes) > 0:  # layer and mask info
                if read_len(width_bytes) > 0:  # layer info
                    raw = fh.read(2)
                    if len(raw) == 2:
                        layers = abs(struct.unpack(">h", raw)[0])
            return {"version": version, "channels": channels, "width": width, "height": height,
                    "depth": depth, "mode": MODES.get(mode, f"mode-{mode}"), "layers": layers}
    except (OSError, struct.error) as exc:
        raise Unreadable(str(exc)) from exc


def compare(before: dict, after: dict) -> list[Finding]:
    out = []
    for key in ("width", "height", "depth", "mode", "version"):
        if before[key] != after[key]:
            out.append(Finding("geometry", f"{key} changed: {before[key]} -> {after[key]}"))
    if after["layers"] < before["layers"]:
        out.append(Finding("layers", f"layers dropped: {before['layers']} -> {after['layers']}"))
    elif after["layers"] > before["layers"]:
        out.append(Finding("layers", f"layer count grew: {before['layers']} -> {after['layers']}", "info"))
    return out
