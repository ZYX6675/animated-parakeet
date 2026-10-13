import json
import random
import sys
import tempfile
import unittest
from pathlib import Path

from parity import corpus, harness, ooxml, psd
from parity.ooxml import Unreadable

ROOT = Path(__file__).resolve().parent
IDENTITY = ["cp", "{input}", "{output}"]
LOSSY = [sys.executable, str(ROOT / "adapters" / "lossy_docx.py"), "{input}", "{output}"]


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.corpus = self.dir / "corpus"
        corpus.generate(self.corpus)

    def tearDown(self):
        self.tmp.cleanup()

    def run_h(self, cmd, **kw):
        return harness.run(cmd, self.corpus, self.dir / "out", **kw)


class OoxmlTests(Base):
    def test_summaries(self):
        d = ooxml.summarize(self.corpus / "with_table.docx")
        self.assertEqual((d["paragraphs"], d["tables"]), (["Intro", "Outro", "cell"], 1))
        x = ooxml.summarize(self.corpus / "book.xlsx")
        self.assertEqual((x["sheets"], x["cells"], x["formulas"]), (["Data", "Summary"], [3, 3], [1, 1]))
        p = ooxml.summarize(self.corpus / "deck.pptx")
        self.assertEqual(len(p["slides"]), 2)

    def test_text_loss_detected(self):
        a = ooxml.summarize(self.corpus / "plain.docx")
        b = dict(a, paragraphs=a["paragraphs"][:-1])
        found = ooxml.compare(a, b)
        self.assertEqual([f.category for f in found], ["text"])

    def test_dropped_style_and_table_detected(self):
        a = ooxml.summarize(self.corpus / "with_table.docx")
        b = dict(a, styles=[], tables=0)
        cats = {f.category for f in ooxml.compare(a, b)}
        self.assertEqual(cats, {"styles", "tables"})

    def test_renamed_parts_are_info_not_failure(self):
        a = ooxml.summarize(self.corpus / "plain.docx")
        b = dict(a, parts=a["parts"][:-1])
        found = ooxml.compare(a, b)
        self.assertTrue(found and all(f.severity == "info" for f in found))

    def test_xlsx_formula_and_sheet_loss(self):
        a = ooxml.summarize(self.corpus / "book.xlsx")
        b = dict(a, formulas=[0, 0], sheets=["Data"])
        self.assertEqual({f.category for f in ooxml.compare(a, b)}, {"formulas", "sheets"})

    def test_pptx_slide_changes(self):
        a = ooxml.summarize(self.corpus / "deck.pptx")
        self.assertEqual(ooxml.compare(a, dict(a, slides=a["slides"][:1]))[0].category, "slides")
        changed = dict(a, slides=[a["slides"][0], ["different"]])
        self.assertEqual(ooxml.compare(a, changed)[0].category, "text")

    def test_unreadable_inputs(self):
        bad = self.dir / "bad.docx"
        bad.write_bytes(b"not a zip")
        with self.assertRaises(Unreadable):
            ooxml.summarize(bad)
        with self.assertRaises(Unreadable):
            ooxml.summarize(self.dir / "x.txt")


class PsdTests(Base):
    def test_summary_and_compare(self):
        a = psd.summarize(self.corpus / "art.psd")
        self.assertEqual((a["width"], a["height"], a["layers"], a["mode"]), (64, 48, 3, "rgb"))
        self.assertEqual({f.category for f in psd.compare(a, dict(a, layers=1, width=65))}, {"layers", "geometry"})
        grew = psd.compare(a, dict(a, layers=5))
        self.assertTrue(all(f.severity == "info" for f in grew))

    def test_not_psd(self):
        bad = self.dir / "bad.psd"
        bad.write_bytes(b"hello world, definitely not a psd file")
        with self.assertRaises(Unreadable):
            psd.summarize(bad)


class HarnessTests(Base):
    def test_identity_passes_everything(self):
        results, _ = self.run_h(IDENTITY)
        self.assertEqual({r.status for r in results}, {"pass"})

    def test_lossy_adapter_fails_docx_only(self):
        results, _ = self.run_h(LOSSY)
        by = {r.file: r for r in results}
        self.assertEqual(by["plain.docx"].status, "fail")
        self.assertEqual(by["with_table.docx"].status, "fail")
        self.assertEqual(by["book.xlsx"].status, "pass")
        summary = harness.summarize_results(results)
        # Each save loses a paragraph, so every docx fails once on the first save and once on the second.
        self.assertEqual(summary["per_kind"]["docx"]["failure_categories"], {"text": 4})
        self.assertTrue(any(f.message.startswith("second save:") for f in by["plain.docx"].findings))
        self.assertEqual(summary["per_kind"]["docx"]["pass_rate"], 0.0)

    def test_crash_timeout_error_and_no_output(self):
        crash, _ = self.run_h(["sh", "-c", "kill -SEGV $$"])
        self.assertEqual({r.status for r in crash}, {"crash"})
        slow, _ = self.run_h(["sleep", "5"], timeout=0.3)
        self.assertEqual({r.status for r in slow}, {"timeout"})
        err, _ = self.run_h(["false"])
        self.assertEqual({r.status for r in err}, {"error"})
        silent, _ = self.run_h(["true"])
        self.assertEqual({r.status for r in silent}, {"error"})
        self.assertIn("no output", silent[0].detail)

    def test_unreadable_output_is_a_reopen_failure(self):
        results, _ = self.run_h(["sh", "-c", "echo junk > {output}"])
        self.assertEqual({r.status for r in results}, {"fail"})
        self.assertEqual(results[0].findings[0].category, "reopen")

    def test_unanalyzable_corpus_file_is_skipped_not_scored(self):
        (self.corpus / "broken.docx").write_bytes(b"junk")
        results, _ = self.run_h(IDENTITY)
        by = {r.file: r for r in results}
        self.assertEqual(by["broken.docx"].status, "skipped")
        summary = harness.summarize_results(results)
        self.assertEqual(summary["per_kind"]["docx"]["scored"], 2)

    def test_fuzz_counts_crashes_and_tolerates_clean_refusals(self):
        _, tolerant = self.run_h(["false"], fuzz=3)
        self.assertTrue(tolerant and all(f.status == "ok" for f in tolerant))
        _, crashing = self.run_h(["sh", "-c", "kill -SEGV $$"], fuzz=3)
        self.assertTrue(all(f.status == "crash" for f in crashing))

    def test_mutation_is_deterministic_for_a_seed(self):
        data = bytes(range(256)) * 4
        for mode in harness.MUTATIONS:
            a = harness.mutate(data, mode, random.Random("1:f"))
            b = harness.mutate(data, mode, random.Random("1:f"))
            self.assertEqual(a, b)
            self.assertNotEqual(a, data)

    def test_report_files_and_markdown(self):
        results, fuzzed = self.run_h(LOSSY, fuzz=3)
        summary = harness.summarize_results(results, fuzzed)
        md = harness.to_markdown(summary, results, "lossy test app")
        self.assertIn("| docx |", md)
        self.assertIn("Failure categories", md)
        self.assertIn("plain.docx", md)
        json.dumps(summary)


if __name__ == "__main__":
    unittest.main()
