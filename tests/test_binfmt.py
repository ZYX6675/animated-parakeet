import unittest

from osl import binfmt


class BinfmtTests(unittest.TestCase):
    def test_entries_are_well_formed(self):
        for name, line in binfmt.registrations().items():
            fields = line.split(":")
            self.assertEqual(fields[0], "")
            self.assertEqual(fields[1], name)
            self.assertEqual(fields[2], "M")
            self.assertEqual(fields[6], binfmt.INTERPRETER)

    def test_fat_macho_magic_is_never_registered(self):
        text = binfmt.conf_text().lower()
        self.assertNotIn("cafebabe", text.replace("\\x", ""))
        self.assertNotIn(r"\xca\xfe", text)

    def test_custom_interpreter(self):
        self.assertIn("/opt/x/open", binfmt.conf_text("/opt/x/open"))


if __name__ == "__main__":
    unittest.main()
