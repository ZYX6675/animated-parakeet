import json
import unittest
from pathlib import Path

from osl import recipes

REPO = Path(__file__).resolve().parent.parent


class RecipeTests(unittest.TestCase):
    def good(self, **kw):
        r = {"id": "x", "name": "X", "runtime": "wine", "status": "untested", "match": {"filename": "x.exe"}}
        r.update(kw)
        return r

    def test_shipped_recipes_are_valid(self):
        for r in recipes.load_dir(REPO / "recipes"):
            r = {k: v for k, v in r.items() if k != "_file"}
            self.assertEqual(recipes.validate(r), [], r["id"])

    def test_missing_fields(self):
        self.assertTrue(recipes.validate({}))

    def test_bad_enums(self):
        self.assertTrue(recipes.validate(self.good(runtime="dosbox")))
        self.assertTrue(recipes.validate(self.good(status="great")))

    def test_works_requires_evidence(self):
        self.assertTrue(recipes.validate(self.good(status="works")))
        self.assertEqual(recipes.validate(self.good(status="works", evidence=["run-001"])), [])

    def test_match_needs_a_key(self):
        self.assertTrue(recipes.validate(self.good(match={})))

    def test_find(self):
        lib = [self.good(match={"sha256": "abc"}), self.good(id="y", match={"filename": "y.exe"})]
        self.assertEqual(recipes.find(lib, sha256="abc")["id"], "x")
        self.assertEqual(recipes.find(lib, filename="y.exe")["id"], "y")
        self.assertIsNone(recipes.find(lib, filename="z.exe"))


if __name__ == "__main__":
    unittest.main()


class WineRecipeSafetyTests(unittest.TestCase):
    def base(self, wine):
        return {"id": "x", "name": "X", "runtime": "wine", "status": "untested",
                "match": {"filename": "x.exe"}, "wine": wine}

    def test_good_wine_section(self):
        wine = {"arch": "win64", "dll_overrides": {"ddraw": "n,b"}, "winetricks": ["corefonts"], "env": {"DXVK_HUD": "0"}}
        self.assertEqual(recipes.validate(self.base(wine)), [])

    def test_dangerous_env_rejected(self):
        for key in ("LD_PRELOAD", "PATH", "WINEPREFIX", "bad-key"):
            self.assertTrue(recipes.validate(self.base({"env": {key: "x"}})), key)

    def test_bad_verbs_and_overrides_rejected(self):
        self.assertTrue(recipes.validate(self.base({"winetricks": ["corefonts; rm -rf /"]})))
        self.assertTrue(recipes.validate(self.base({"dll_overrides": {"ddraw": "evil"}})))
        self.assertTrue(recipes.validate(self.base({"arch": "win128"})))

    def test_newline_in_env_value_rejected(self):
        self.assertTrue(recipes.validate(self.base({"env": {"A": "x\nB=y"}})))
