"""Identify executable formats (ELF, PE, Mach-O) from file headers.

Only header bytes are read. Nothing here executes or decompiles the file.
"""
from __future__ import annotations

import struct
from dataclasses import dataclass
from pathlib import Path

ELF_MACHINES = {0x03: "x86", 0x3E: "x86_64", 0x28: "arm", 0xB7: "arm64", 0xF3: "riscv"}
PE_MACHINES = {0x014C: "x86", 0x8664: "x86_64", 0x01C4: "arm", 0xAA64: "arm64"}
MACHO_CPUS = {7: "x86", 0x01000007: "x86_64", 12: "arm", 0x0100000C: "arm64"}

# magic -> byte order for thin Mach-O files
_MACHO_THIN = {
    b"\xfe\xed\xfa\xce": ">",
    b"\xfe\xed\xfa\xcf": ">",
    b"\xce\xfa\xed\xfe": "<",
    b"\xcf\xfa\xed\xfe": "<",
}
_FAT_MAGICS = {b"\xca\xfe\xba\xbe": 20, b"\xca\xfe\xba\xbf": 32}
HEADER_BYTES = 64 * 1024


@dataclass(frozen=True)
class BinaryInfo:
    kind: str  # elf | pe | macho | script | unknown
    archs: tuple[str, ...] = ()
    detail: str = ""


def detect_bytes(head: bytes) -> BinaryInfo:
    if head[:4] == b"\x7fELF" and len(head) >= 20:
        order = "<" if head[5] == 1 else ">"
        (machine,) = struct.unpack_from(order + "H", head, 18)
        return BinaryInfo("elf", (ELF_MACHINES.get(machine, f"unknown-{machine:#x}"),))

    if head[:2] == b"MZ":
        if len(head) >= 0x40:
            (off,) = struct.unpack_from("<I", head, 0x3C)
            if off + 6 <= len(head) and head[off : off + 4] == b"PE\0\0":
                (machine,) = struct.unpack_from("<H", head, off + 4)
                return BinaryInfo("pe", (PE_MACHINES.get(machine, f"unknown-{machine:#x}"),))
        return BinaryInfo("unknown", detail="MZ header without a PE header (DOS or legacy)")

    magic = head[:4]
    if magic in _MACHO_THIN and len(head) >= 8:
        (cpu,) = struct.unpack_from(_MACHO_THIN[magic] + "I", head, 4)
        return BinaryInfo("macho", (MACHO_CPUS.get(cpu, f"unknown-{cpu:#x}"),))

    if magic in _FAT_MAGICS and len(head) >= 8:
        (count,) = struct.unpack_from(">I", head, 4)
        if count > 30:  # the same magic is used by Java class files
            return BinaryInfo("unknown", detail="Java class file")
        width = _FAT_MAGICS[magic]
        archs = []
        for i in range(count):
            at = 8 + i * width
            if at + 4 > len(head):
                break
            (cpu,) = struct.unpack_from(">I", head, at)
            archs.append(MACHO_CPUS.get(cpu, f"unknown-{cpu:#x}"))
        return BinaryInfo("macho", tuple(archs), "universal binary")

    if head[:2] == b"#!":
        first = head.split(b"\n", 1)[0].decode("utf-8", "replace")
        return BinaryInfo("script", detail=first)

    return BinaryInfo("unknown")


def detect_file(path: str | Path) -> BinaryInfo:
    with open(path, "rb") as fh:
        return detect_bytes(fh.read(HEADER_BYTES))
