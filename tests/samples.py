"""Synthetic header-only samples. No real third-party binaries are used or needed."""
import struct


def elf(machine=0x3E):
    h = bytearray(64)
    h[0:4] = b"\x7fELF"
    h[4] = 2  # 64-bit
    h[5] = 1  # little endian
    struct.pack_into("<H", h, 18, machine)
    return bytes(h)


def pe(machine=0x8664, e_lfanew=0x80):
    h = bytearray(0x200)
    h[0:2] = b"MZ"
    struct.pack_into("<I", h, 0x3C, e_lfanew)
    h[e_lfanew : e_lfanew + 4] = b"PE\0\0"
    struct.pack_into("<H", h, e_lfanew + 4, machine)
    return bytes(h)


def macho(cpu=0x01000007):
    return b"\xcf\xfa\xed\xfe" + struct.pack("<I", cpu) + bytes(24)


def fat(cpus):
    out = b"\xca\xfe\xba\xbe" + struct.pack(">I", len(cpus))
    for c in cpus:
        out += struct.pack(">IIIII", c, 0, 0, 0, 0)
    return out


def java_class():
    return b"\xca\xfe\xba\xbe" + struct.pack(">HH", 0, 52) + bytes(32)
