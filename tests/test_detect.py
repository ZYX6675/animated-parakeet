import unittest

from osl.detect import detect_bytes
from tests import samples as s


class DetectTests(unittest.TestCase):
    def test_elf(self):
        self.assertEqual(detect_bytes(s.elf(0x3E)).archs, ("x86_64",))
        self.assertEqual(detect_bytes(s.elf(0xB7)).archs, ("arm64",))

    def test_pe(self):
        info = detect_bytes(s.pe(0x8664))
        self.assertEqual((info.kind, info.archs), ("pe", ("x86_64",)))
        self.assertEqual(detect_bytes(s.pe(0xAA64)).archs, ("arm64",))
        self.assertEqual(detect_bytes(s.pe(0x014C)).archs, ("x86",))

    def test_mz_without_pe_is_unknown(self):
        self.assertEqual(detect_bytes(b"MZ" + bytes(100)).kind, "unknown")

    def test_macho_thin(self):
        info = detect_bytes(s.macho(0x0100000C))
        self.assertEqual((info.kind, info.archs), ("macho", ("arm64",)))

    def test_macho_universal(self):
        info = detect_bytes(s.fat([0x01000007, 0x0100000C]))
        self.assertEqual((info.kind, info.archs), ("macho", ("x86_64", "arm64")))

    def test_java_class_is_not_macho(self):
        self.assertEqual(detect_bytes(s.java_class()).kind, "unknown")

    def test_script_and_junk(self):
        self.assertEqual(detect_bytes(b"#!/bin/sh\necho hi\n").kind, "script")
        self.assertEqual(detect_bytes(b"hello").kind, "unknown")
        self.assertEqual(detect_bytes(b"").kind, "unknown")

    def test_truncated_headers_do_not_crash(self):
        for blob in (b"\x7fELF", b"MZ", b"\xcf\xfa\xed\xfe", b"\xca\xfe\xba\xbe"):
            detect_bytes(blob)


if __name__ == "__main__":
    unittest.main()
