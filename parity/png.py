"""Minimal PNG reader and writer (standard library only).

Reads 8-bit, non-interlaced PNGs (grayscale, RGB, palette, gray+alpha, RGBA) and returns RGB,
compositing transparency onto white. Anything else raises PngError so the caller can say the
comparison was skipped instead of guessing.
"""
from __future__ import annotations

import struct
import zlib
from dataclasses import dataclass

SIGNATURE = b"\x89PNG\r\n\x1a\n"
CHANNELS = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}


class PngError(Exception):
    pass


@dataclass(frozen=True)
class Image:
    width: int
    height: int
    rgb: bytes  # width * height * 3


def _paeth(a, b, c):
    p = a + b - c
    pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
    return a if pa <= pb and pa <= pc else (b if pb <= pc else c)


def _unfilter(raw: bytes, height: int, stride: int, bpp: int) -> bytearray:
    out = bytearray(height * stride)
    prev = bytearray(stride)
    pos = 0
    for y in range(height):
        ftype = raw[pos]
        line = bytearray(raw[pos + 1 : pos + 1 + stride])
        pos += 1 + stride
        if ftype == 1:
            for i in range(bpp, stride):
                line[i] = (line[i] + line[i - bpp]) & 255
        elif ftype == 2:
            for i in range(stride):
                line[i] = (line[i] + prev[i]) & 255
        elif ftype == 3:
            for i in range(stride):
                left = line[i - bpp] if i >= bpp else 0
                line[i] = (line[i] + ((left + prev[i]) >> 1)) & 255
        elif ftype == 4:
            for i in range(stride):
                left = line[i - bpp] if i >= bpp else 0
                upleft = prev[i - bpp] if i >= bpp else 0
                line[i] = (line[i] + _paeth(left, prev[i], upleft)) & 255
        elif ftype != 0:
            raise PngError(f"unknown filter type {ftype}")
        out[y * stride : (y + 1) * stride] = line
        prev = line
    return out


def read_png(path, max_pixels: int = 4_000_000) -> Image:
    try:
        with open(path, "rb") as fh:
            data = fh.read()
    except OSError as exc:
        raise PngError(str(exc)) from exc
    if data[:8] != SIGNATURE:
        raise PngError("not a PNG file")
    pos, header, palette, idat = 8, None, b"", []
    while pos + 8 <= len(data):
        length, ctype = struct.unpack(">I4s", data[pos : pos + 8])
        body = data[pos + 8 : pos + 8 + length]
        if len(body) < length:
            raise PngError("truncated PNG")
        if ctype == b"IHDR":
            header = struct.unpack(">IIBBBBB", body)
        elif ctype == b"PLTE":
            palette = body
        elif ctype == b"IDAT":
            idat.append(body)
        elif ctype == b"IEND":
            break
        pos += 12 + length
    if header is None or not idat:
        raise PngError("missing header or image data")
    width, height, depth, ctype, _, _, interlace = header
    if depth != 8 or interlace != 0 or ctype not in CHANNELS:
        raise PngError(f"unsupported PNG variant (depth {depth}, color type {ctype}, interlace {interlace})")
    if width * height > max_pixels or width == 0 or height == 0:
        raise PngError(f"image too large to compare ({width}x{height})")
    ch = CHANNELS[ctype]
    stride = width * ch
    expected = height * (1 + stride)
    try:
        raw = zlib.decompressobj().decompress(b"".join(idat), expected + 16)
    except zlib.error as exc:
        raise PngError(f"corrupt image data: {exc}") from exc
    if len(raw) < expected:
        raise PngError("image data shorter than the header says")
    px = _unfilter(raw, height, stride, ch)

    rgb = bytearray(width * height * 3)
    n = width * height
    if ctype == 2:
        rgb[:] = px
    elif ctype == 0:
        for i in range(n):
            rgb[3 * i : 3 * i + 3] = bytes((px[i],)) * 3
    elif ctype == 3:
        if len(palette) < 3:
            raise PngError("palette image without a palette")
        for i in range(n):
            j = 3 * px[i]
            rgb[3 * i : 3 * i + 3] = palette[j : j + 3]
    elif ctype == 4:
        for i in range(n):
            g, a = px[2 * i], px[2 * i + 1]
            v = (g * a + 255 * (255 - a)) // 255
            rgb[3 * i : 3 * i + 3] = bytes((v,)) * 3
    else:  # RGBA
        for i in range(n):
            r, g, b, a = px[4 * i : 4 * i + 4]
            rgb[3 * i : 3 * i + 3] = bytes(((c * a + 255 * (255 - a)) // 255 for c in (r, g, b)))
    return Image(width, height, bytes(rgb))


def _chunk(kind: bytes, body: bytes) -> bytes:
    return struct.pack(">I", len(body)) + kind + body + struct.pack(">I", zlib.crc32(kind + body) & 0xFFFFFFFF)


def write_png(path, width: int, height: int, rgb: bytes) -> None:
    stride = width * 3
    raw = b"".join(b"\x00" + rgb[y * stride : (y + 1) * stride] for y in range(height))
    blob = (SIGNATURE + _chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
            + _chunk(b"IDAT", zlib.compress(raw, 6)) + _chunk(b"IEND", b""))
    with open(path, "wb") as fh:
        fh.write(blob)
