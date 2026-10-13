from __future__ import annotations

import argparse
import json
import shlex
import sys
from dataclasses import asdict
from pathlib import Path

from . import corpus, harness, visual


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="parity", description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)

    g = sub.add_parser("gen-corpus", help="write tiny synthetic samples (for testing the harness only)")
    g.add_argument("directory")

    r = sub.add_parser("run", help="round-trip every corpus file through an adapter and score it")
    r.add_argument("--adapter", required=True, help="command with {input} and {output}, e.g. 'cp {input} {output}'")
    r.add_argument("--corpus", required=True)
    r.add_argument("--out", required=True)
    r.add_argument("--app", default="app under test")
    r.add_argument("--timeout", type=float, default=60)
    r.add_argument("--fuzz", type=int, default=0, help="corrupted variants per file")
    r.add_argument("--seed", type=int, default=0)
    r.add_argument("--render-ref", help="reference renderer: command with {input} and {outdir} (writes page-N.png)")
    r.add_argument("--render-app", help="the app's own renderer, same contract; enables open-fidelity checks")
    r.add_argument("--max-changed-fraction", type=float, default=0.02, help="fail a page if more than this share of pixels changed")
    r.add_argument("--max-mean-diff", type=float, default=0.01, help="fail a page if mean pixel difference exceeds this (0-1)")
    r.add_argument("--min-pass-rate", type=float, default=None, help="exit 1 if any type scores below this (0-1)")
    args = ap.parse_args(argv)

    if args.cmd == "gen-corpus":
        for p in corpus.generate(args.directory):
            print(p)
        return 0

    out = Path(args.out)
    vis = None
    if args.render_ref:
        vis = visual.VisualConfig(shlex.split(args.render_ref), shlex.split(args.render_app) if args.render_app else None,
                                  max_changed_fraction=args.max_changed_fraction, max_mean_diff=args.max_mean_diff)
    elif args.render_app:
        ap.error("--render-app needs --render-ref")
    results, fuzzed = harness.run(shlex.split(args.adapter), Path(args.corpus), out, args.timeout, args.fuzz, args.seed, vis)
    summary = harness.summarize_results(results, fuzzed)
    (out / "report.json").write_text(json.dumps(
        {"app": args.app, "summary": summary, "results": [asdict(r) for r in results],
         "fuzz": [asdict(f) for f in fuzzed]}, indent=2, default=str))
    md = harness.to_markdown(summary, results, args.app)
    (out / "report.md").write_text(md)
    print(md)

    bad = any(v["crash"] or v["timeout"] for v in summary["fuzz"].values())
    if args.min_pass_rate is not None:
        bad |= any(v["pass_rate"] is not None and v["pass_rate"] < args.min_pass_rate for v in summary["per_kind"].values())
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
