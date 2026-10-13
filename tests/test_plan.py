import unittest
from pathlib import Path

from osl.detect import detect_bytes
from osl.plan import make_plan
from osl.runtime import decide
from tests import samples as s

ROOT = Path("/tmp/prefixes")


def wine_decision():
    return decide(detect_bytes(s.pe()), Path("/tmp/setup.exe"), "x86_64", ROOT)


RECIPE = {
    "id": "demo", "name": "Demo", "runtime": "wine", "status": "works", "evidence": ["run-1"],
    "match": {"filename": "setup.exe"},
    "wine": {"arch": "win32", "dll_overrides": {"ddraw": "n,b", "d3d9": "b"},
             "winetricks": ["corefonts", "vcrun2019"], "env": {"DXVK_HUD": "0"}},
}


class PlanTests(unittest.TestCase):
    def test_no_recipe_first_run_initialises_prefix_only(self):
        p = make_plan(wine_decision(), None, provisioned=False)
        self.assertEqual(len(p.setup), 1)
        self.assertIn("wineboot", p.setup[0])
        self.assertEqual(p.run[-2:], ("wine", "/tmp/setup.exe"))
        self.assertTrue(any("no recipe" in n for n in p.notes))

    def test_recipe_adds_arch_overrides_env_and_verbs(self):
        d = wine_decision()
        p = make_plan(d, RECIPE, provisioned=False)
        self.assertIn("WINEARCH=win32", p.setup[0])
        self.assertEqual(p.setup[1][-3:], ("-q", "corefonts", "vcrun2019"))
        self.assertIn("WINEDLLOVERRIDES=d3d9=b;ddraw=n,b", p.run)
        self.assertIn("DXVK_HUD=0", p.run)
        self.assertIn(f"WINEPREFIX={d.prefix}", p.run)

    def test_provisioned_prefix_skips_setup(self):
        self.assertEqual(make_plan(wine_decision(), RECIPE, provisioned=True).setup, ())

    def test_status_notes(self):
        broken = dict(RECIPE, status="broken", evidence=[], notes="crashes at start")
        note = make_plan(wine_decision(), broken, True).notes[0]
        self.assertIn("broken", note)
        self.assertIn("crashes at start", note)
        untested = dict(RECIPE, status="untested", evidence=[])
        self.assertIn("no evidence", make_plan(wine_decision(), untested, True).notes[0])

    def test_non_wine_runtime_passes_command_through(self):
        d = decide(detect_bytes(s.elf()), Path("/tmp/a.out"), "x86_64", ROOT)
        p = make_plan(d, None, False)
        self.assertEqual((p.setup, p.run), ((), d.command))


if __name__ == "__main__":
    unittest.main()
