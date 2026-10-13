import struct
import sys
import tempfile
import unittest
import zlib
from pathlib import Path

from parity import __main__ as cli
from parity import corpus, harness, png, visual

ROOT = Path(__file__).resolve().parent
FAKE = str(ROOT / "adapters" / "fake_render.py")
IDENTITY = ["cp", "{input}", "{output}"]
LOSSY = [sys.executable, str(ROOT / "adapters" / "lossy_docx.py"), "{input}", "{output}"]


def renderer(mode="same"):
    return [sys.executable, FAKE, "{input}", "{outdir}", mode]


def encode(width, height, rgb, ctype=2, ftypes=(0,), palette=None, depth=8, interlace=0):
    ch = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}[ctype]
    stride, prev, rows = width * ch, bytearray(width * ch), []
    for y in range(height):
        line = bytearray(rgb[y * stride : (y + 1) * stride])
        ft = ftypes[y % len(ftypes)]
        out = bytearray(stride)
        for i in range(stride):
            left = line[i - ch] if i >= ch else 0
            up = prev[i]
            ul = prev[i - ch] if i >= ch else 0
            pred = {0: 0, 1: left, 2: up, 3: (left + up) >> 1, 4: png._paeth(left, up, ul)}[ft]
            out[i] = (line[i] - pred) & 255
        rows.append(bytes([ft]) + bytes(out))
        prev = line
    body = png._chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, depth, ctype, 0, 0, interlace))
    if palette:
        body += png._chunk(b"PLTE", palette)
    body += png._chunk(b"IDAT", zlib.compress(b"".join(rows))) + png._chunk(b"IEND", b"")
    return png.SIGNATURE + body


class PngTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def load(self, blob):
        p = self.dir / "t.png"
        p.write_bytes(blob)
        return png.read_png(p)

    def test_all_filter_types_decode(self):
        w, h = 7, 8
        rgb = bytes((x * 37 + y * 11 + c * 5) & 255 for y in range(h) for x in range(w) for c in range(3))
        img = self.load(encode(w, h, rgb, ftypes=(0, 1, 2, 3, 4)))
        self.assertEqual((img.width, img.height, img.rgb), (w, h, rgb))

    def test_writer_roundtrip(self):
        rgb = bytes(range(60)) + bytes(60)
        p = self.dir / "w.png"
        png.write_png(p, 10, 4, rgb)
        self.assertEqual(png.read_png(p).rgb, rgb)

    def test_palette_gray_and_alpha(self):
        pal = bytes([255, 0, 0, 0, 255, 0])
        self.assertEqual(self.load(encode(2, 1, bytes([0, 1]), ctype=3, palette=pal)).rgb, bytes([255, 0, 0, 0, 255, 0]))
        self.assertEqual(self.load(encode(2, 1, bytes([0, 200]), ctype=0)).rgb, bytes([0, 0, 0, 200, 200, 200]))
        rgba = bytes([255, 0, 0, 255, 255, 0, 0, 0])  # opaque red, fully transparent red
        self.assertEqual(self.load(encode(2, 1, rgba, ctype=6)).rgb, bytes([255, 0, 0, 255, 255, 255]))

    def test_unsupported_and_bad_files(self):
        for blob in (encode(1, 1, bytes(6), depth=16), encode(1, 1, bytes(3), interlace=1), b"nope", png.SIGNATURE + b"\x00"):
            with self.assertRaises(png.PngError):
                self.load(blob)

    def test_size_guard(self):
        p = self.dir / "big.png"
        png.write_png(p, 50, 50, bytes(7500))
        with self.assertRaises(png.PngError):
            png.read_png(p, max_pixels=100)


class MetricTests(unittest.TestCase):
    def test_identical_and_changed(self):
        a = bytes(12)
        self.assertEqual(visual.diff_metrics(a, a, 16), (0.0, 0.0))
        b = bytearray(12)
        b[0:3] = b"\xff\xff\xff"  # one of four pixels fully changed
        mean, changed = visual.diff_metrics(a, bytes(b), 16)
        self.assertEqual(changed, 0.25)
        self.assertAlmostEqual(mean, 3 * 255 / (12 * 255))

    def test_small_difference_is_within_tolerance(self):
        a = bytes(12)
        b = bytes([10] * 12)
        self.assertEqual(visual.diff_metrics(a, b, 16)[1], 0.0)


class VisualHarnessTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.corpus = self.dir / "c"
        corpus.generate(self.corpus)

    def tearDown(self):
        self.tmp.cleanup()

    def run_v(self, adapter, ref, app=None):
        cfg = visual.VisualConfig(ref, app)
        results, _ = harness.run(adapter, self.corpus, self.dir / "out", vis=cfg)
        return {r.file: r for r in results}

    def vis(self, result):
        return [f for f in result.findings if f.category == "visual"]

    def test_matching_renders_pass(self):
        res = self.run_v(IDENTITY, renderer(), renderer())
        self.assertEqual({r.status for r in res.values()}, {"pass"})

    def test_big_difference_in_app_render_fails_open_fidelity(self):
        res = self.run_v(IDENTITY, renderer(), renderer("big_noise"))
        r = res["plain.docx"]
        self.assertEqual(r.status, "fail")
        self.assertIn("open fidelity", self.vis(r)[0].message)
        self.assertTrue((self.dir / "out" / "visual" / "plain" / "open.page1.diff.png").exists())

    def test_small_noise_is_tolerated(self):
        res = self.run_v(IDENTITY, renderer(), renderer("small_noise"))
        self.assertEqual({r.status for r in res.values()}, {"pass"})

    def test_page_count_mismatch(self):
        res = self.run_v(IDENTITY, renderer(), renderer("two_pages"))
        self.assertIn("page count 1 -> 2", self.vis(res["plain.docx"])[0].message)

    def test_save_fidelity_catches_a_lossy_save(self):
        res = self.run_v(LOSSY, renderer())
        self.assertTrue(any("save fidelity" in f.message for f in self.vis(res["plain.docx"])))
        self.assertEqual(self.vis(res["book.xlsx"]), [])

    def test_broken_reference_renderer_is_info_not_failure(self):
        res = self.run_v(IDENTITY, ["false"])
        r = res["plain.docx"]
        self.assertEqual(r.status, "pass")
        self.assertTrue(all(f.severity == "info" for f in self.vis(r)) and self.vis(r))

    def test_broken_app_renderer_is_a_failure(self):
        res = self.run_v(IDENTITY, renderer(), ["false"])
        self.assertEqual(res["plain.docx"].status, "fail")
        self.assertIn("app could not render", self.vis(res["plain.docx"])[0].message)

    def test_cli_requires_reference_for_app_renderer(self):
        with self.assertRaises(SystemExit) as ctx:
            cli.main(["run", "--adapter", "cp {input} {output}", "--corpus", str(self.corpus),
                      "--out", str(self.dir / "o"), "--render-app", "x {input} {outdir}"])
        self.assertEqual(ctx.exception.code, 2)

    def test_cli_end_to_end_reports_visual_category(self):
        rc = cli.main(["run", "--adapter", " ".join(LOSSY), "--corpus", str(self.corpus), "--out", str(self.dir / "o2"),
                       "--render-ref", f"{sys.executable} {FAKE} {{input}} {{outdir}} same"])
        self.assertEqual(rc, 0)  # no pass-rate gate requested
        report = (self.dir / "o2" / "report.md").read_text()
        self.assertIn("visual", report)


if __name__ == "__main__":
    unittest.main()
