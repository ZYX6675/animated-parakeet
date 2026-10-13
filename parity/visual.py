"""Visual comparison of rendered pages.

Two checks, both optional:
  open fidelity: the app's own render of a file vs the reference renderer's render of it.
  save fidelity: the reference renderer's render of the file the app SAVED vs the original.
A renderer is a command with {input} and {outdir}; it must write page-1.png, page-2.png, ...
into {outdir}. Typical reference chain: a trusted app exports to PDF, then pdftoppm makes PNGs.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .findings import Finding
from .png import PngError, read_png, write_png
from .runner import run_command


@dataclass
class VisualConfig:
    ref_cmd: list
    app_cmd: list | None = None
    tolerance: int = 16               # per-channel difference (0-255) below which a pixel counts as unchanged
    max_changed_fraction: float = 0.02
    max_mean_diff: float = 0.01
    max_pixels: int = 4_000_000


def render(cmd, src: Path, outdir: Path, timeout: float):
    outdir.mkdir(parents=True, exist_ok=True)
    for old in outdir.glob("*.png"):
        old.unlink()
    state, detail = run_command(cmd, {"input": src, "outdir": outdir}, timeout)
    if state != "ok":
        return state, detail
    pages = sorted(outdir.glob("*.png"), key=lambda p: (len(p.stem), p.stem))
    return ("ok", pages) if pages else ("error", "renderer wrote no PNG pages")


def diff_metrics(a: bytes, b: bytes, tolerance: int):
    total = sum(abs(x - y) for x, y in zip(a, b))
    mean = total / (len(a) * 255) if a else 0.0
    changed = 0
    for i in range(0, len(a), 3):
        if (abs(a[i] - b[i]) > tolerance or abs(a[i + 1] - b[i + 1]) > tolerance
                or abs(a[i + 2] - b[i + 2]) > tolerance):
            changed += 1
    return mean, changed / (len(a) // 3 or 1)


def _write_diff(path: Path, a, b, tolerance: int):
    out = bytearray(len(a.rgb))
    for i in range(0, len(a.rgb), 3):
        px = a.rgb[i : i + 3]
        if any(abs(px[k] - b.rgb[i + k]) > tolerance for k in range(3)):
            out[i : i + 3] = b"\xff\x00\x00"
        else:
            g = (px[0] + px[1] + px[2]) // 3
            v = 255 - (255 - g) // 3  # faded copy of the original for context
            out[i : i + 3] = bytes((v, v, v))
    path.parent.mkdir(parents=True, exist_ok=True)
    write_png(path, a.width, a.height, bytes(out))


def compare_pages(label: str, expected, actual, cfg: VisualConfig, diff_dir: Path, tag: str):
    if len(expected) != len(actual):
        return [Finding("visual", f"{label}: page count {len(expected)} -> {len(actual)}")]
    findings = []
    for n, (pa, pb) in enumerate(zip(expected, actual), 1):
        try:
            ia, ib = read_png(pa, cfg.max_pixels), read_png(pb, cfg.max_pixels)
        except PngError as exc:
            findings.append(Finding("visual", f"{label}: page {n} not compared ({exc})", "info"))
            continue
        if (ia.width, ia.height) != (ib.width, ib.height):
            findings.append(Finding("visual", f"{label}: page {n} size {ia.width}x{ia.height} -> {ib.width}x{ib.height}"))
            continue
        mean, changed = diff_metrics(ia.rgb, ib.rgb, cfg.tolerance)
        if changed > cfg.max_changed_fraction or mean > cfg.max_mean_diff:
            _write_diff(diff_dir / f"{tag}.page{n}.diff.png", ia, ib, cfg.tolerance)
            findings.append(Finding(
                "visual", f"{label}: page {n} differs ({changed:.1%} of pixels changed, mean difference {mean:.1%}); "
                          f"diff image: {tag}.page{n}.diff.png"))
    return findings


def check(cfg: VisualConfig, src: Path, dst: Path, rel: Path, out_dir: Path, timeout: float):
    base = out_dir / "visual" / rel.with_suffix("")
    state, ref_src = render(cfg.ref_cmd, src, base / "ref-src", timeout)
    if state != "ok":
        return [Finding("visual", f"reference renderer could not render the original ({state}); visual check skipped", "info")]
    findings = []
    if cfg.app_cmd:
        state, app_src = render(cfg.app_cmd, src, base / "app-src", timeout)
        if state != "ok":
            findings.append(Finding("visual", f"app could not render a file it opened ({state}: {app_src})"))
        else:
            findings += compare_pages("open fidelity (app vs reference)", ref_src, app_src, cfg, base, "open")
    state, ref_dst = render(cfg.ref_cmd, dst, base / "ref-dst", timeout)
    if state != "ok":
        findings.append(Finding("visual", f"reference renderer cannot render the file the app saved ({state})"))
    else:
        findings += compare_pages("save fidelity (saved file vs original)", ref_src, ref_dst, cfg, base, "save")
    return findings
