import unittest
from pathlib import Path

from osl.detect import detect_bytes
from osl.runtime import decide, prefix_for
from tests import samples as s

ROOT = Path("/tmp/prefixes")


def run(blob, host, name="app.bin"):
    return decide(detect_bytes(blob), Path("/tmp") / name, host, ROOT)


class RuntimeTests(unittest.TestCase):
    def test_native_elf(self):
        d = run(s.elf(0x3E), "x86_64")
        self.assertEqual((d.runtime, d.supported), ("native", True))

    def test_foreign_elf_unsupported(self):
        self.assertFalse(run(s.elf(0xB7), "x86_64").supported)

    def test_pe_goes_to_wine_with_own_prefix(self):
        d = run(s.pe(0x8664), "x86_64", "setup.exe")
        self.assertEqual(d.runtime, "wine")
        self.assertTrue(any(part.startswith("WINEPREFIX=/tmp/prefixes/setup-") for part in d.command))

    def test_two_apps_get_different_prefixes(self):
        a = prefix_for(Path("/tmp/a/setup.exe"), ROOT)
        b = prefix_for(Path("/tmp/b/setup.exe"), ROOT)
        self.assertNotEqual(a, b)

    def test_arm64_pe_unsupported(self):
        self.assertFalse(run(s.pe(0xAA64), "x86_64").supported)

    def test_macho_x86_goes_to_darling(self):
        self.assertEqual(run(s.macho(0x01000007), "x86_64").runtime, "darling")

    def test_universal_with_x86_slice_goes_to_darling(self):
        self.assertEqual(run(s.fat([0x01000007, 0x0100000C]), "x86_64").runtime, "darling")

    def test_arm64_only_macho_explains_why(self):
        d = run(s.macho(0x0100000C), "x86_64")
        self.assertFalse(d.supported)
        self.assertIn("Apple Silicon", d.reason)

    def test_unknown_is_unsupported(self):
        self.assertFalse(run(b"junk", "x86_64").supported)


if __name__ == "__main__":
    unittest.main()
