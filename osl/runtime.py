"""Choose a runtime for a detected binary and build the launch command."""
from __future__ import annotations

import hashlib
import platform
import re
from dataclasses import dataclass
from pathlib import Path

from .detect import BinaryInfo


@dataclass(frozen=True)
class Decision:
    runtime: str  # native | wine | darling | none
    supported: bool
    reason: str
    command: tuple[str, ...] = ()
    prefix: str = ""


def host_arch() -> str:
    m = platform.machine().lower()
    return {"amd64": "x86_64", "x86_64": "x86_64", "aarch64": "arm64", "arm64": "arm64"}.get(m, m)


def prefix_for(path: Path, prefix_root: Path) -> Path:
    """One isolated Wine prefix per app, keyed by name and full path."""
    stem = re.sub(r"[^A-Za-z0-9_.-]", "_", path.stem) or "app"
    digest = hashlib.sha256(str(path.resolve()).encode()).hexdigest()[:8]
    return prefix_root / f"{stem}-{digest}"


def decide(info: BinaryInfo, path: Path, host: str, prefix_root: Path) -> Decision:
    path = Path(path)
    if info.kind == "script":
        return Decision("native", True, f"script ({info.detail})", (str(path),))

    if info.kind == "elf":
        arch = info.archs[0]
        if arch == host or (host == "x86_64" and arch == "x86"):
            return Decision("native", True, f"ELF {arch} on {host} host", (str(path),))
        return Decision("none", False, f"ELF {arch} binary on {host} host needs emulation (not planned)")

    if info.kind == "pe":
        arch = info.archs[0]
        if host != "x86_64":
            return Decision("none", False, f"Windows layer targets x86-64 hosts only in Phase 3 (host is {host})")
        if arch in ("x86", "x86_64"):
            prefix = prefix_for(path, prefix_root)
            cmd = ("env", f"WINEPREFIX={prefix}", "wine", str(path))
            return Decision("wine", True, f"PE {arch} via Wine, prefix {prefix.name}", cmd, str(prefix))
        return Decision("none", False, f"PE {arch} binary on x86-64 host is not supported")

    if info.kind == "macho":
        if host != "x86_64":
            return Decision("none", False, f"Darling path targets x86-64 hosts only (host is {host})")
        if "x86_64" in info.archs:
            return Decision("darling", True, "Mach-O with an x86_64 slice via Darling", ("darling", str(path)))
        return Decision(
            "none", False,
            f"Mach-O {'/'.join(info.archs) or 'unknown'} only; Apple Silicon binaries need an ARM host or emulation",
        )

    return Decision("none", False, info.detail or "unrecognized file format")
