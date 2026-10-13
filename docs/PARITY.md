# Parity measurement

Purpose: replace self-reported "percent of Photoshop/Word" claims with numbers from real files.

## What it measures today

For every file in a corpus the harness does a **round trip**: the app under test opens the file and
saves a copy, then opens and saves that copy again. It then compares structure before and after.

| Type | Checked |
| --- | --- |
| DOCX | paragraph text and order, tables, drawings, media files, style definitions |
| XLSX | sheet names, cells per sheet, formula counts, shared strings |
| PPTX | slide count, text on each slide |
| PSD/PSB | width, height, bit depth, color mode, layer count (header level only) |
| All | the app can reopen its own output; second-save loss; crash and hang on corrupt input (fuzzing) |

Each file ends as `pass`, `fail` (with categories), `crash`, `timeout`, `error`, or `skipped`
(the corpus file itself could not be analyzed, so it is not scored). Renamed or dropped parts are
reported as `info` only, because real apps legitimately reorganize packages.

## What it does not measure (yet)

- **Visual fidelity without a renderer.** Structural checks alone say "does not lose content", not
  "looks the same". Turn on the visual checks below to cover appearance.
- Formula **results**, fonts, tracked changes, comments, charts, embedded objects, and PSD layer
  pixel data or effects.
- Performance on large files.

## Visual checks (optional)

Give the harness a **reference renderer** (a trusted app, for example a headless export to PDF followed
by `pdftoppm`, wrapped in a script) and it adds two checks per file:

- **Save fidelity:** render the file the app saved and compare it with the render of the original.
  This answers "does the reference app show what our app saved?" and needs only the reference renderer.
- **Open fidelity:** with `--render-app` too, compare the app's own render of the original with the
  reference render. This answers "does our app show the file the way the reference does?"

A renderer is a command with `{input}` and `{outdir}` that writes `page-1.png`, `page-2.png`, and so on.
Pages are compared pixel by pixel after a per-channel tolerance (default 16 of 255); a page fails if
more than 2% of pixels changed or the mean difference is over 1% (both configurable). Failing pages get a
diff image (changed pixels in red) next to the report. Page-count and page-size changes also fail.

Limits: this is a pixel comparison, so anti-aliasing and font differences between renderers show up as
noise; tune the thresholds on a corpus where you know the answer. Only 8-bit non-interlaced PNGs up to
4 million pixels are read (about A4 at 150 dpi); anything else is reported as "not compared", never
silently passed. Decoding costs about half a second per A4 page at 100 dpi in the worst case.

## Using it

```
python3 -m parity gen-corpus samples/              # tiny synthetic files, for testing the harness only
python3 -m parity run \
    --adapter "my-app-roundtrip {input} {output}" \
    --corpus path/to/real/corpus --out results/ \
    --app "WordCraft nightly" --fuzz 5 --seed 1 --min-pass-rate 0.9

# add visual checks
    --render-ref "ref-render {input} {outdir}" --render-app "my-app-render {input} {outdir}"
```

An **adapter** is any command with `{input}` and `{output}`: it must make the app open the input and
save to the output (a headless export flag or a small script around the app's automation interface).
Writing the adapter for each app is the real integration work. The run writes `report.md` and
`report.json`, and exits 1 on any fuzz crash or timeout, or if a file type scores below
`--min-pass-rate`, so it can gate CI.

## Corpus requirements

The synthetic files are minimal and are **not** guaranteed to open in real office software. A real
run needs real documents: public corpora, user-donated files (with permission), and files generated
by the original apps. Check licensing before collecting any of them, including whether you may keep
reference outputs from commercial apps (open question in the clean-room policy).

## Safety

Corpus files are untrusted. The analyzers limit part sizes and part counts and check archive integrity,
but run the harness in a throwaway container or VM, and never point it at a corpus you have not
chosen. Python's XML parser is used without extra hardening; if you process hostile files at scale,
consider adding `defusedxml`.

## Publishing results

Publish the per-type table and the failure categories from `report.md` for every release, with the
corpus size and date. A number without its corpus is not a measurement.
