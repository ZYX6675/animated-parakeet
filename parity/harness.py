"""Run an app (through an adapter command) over a corpus and score the results.

An adapter is any command with {input} and {output} placeholders that makes the app under test
open the input file and save it to the output path, for example:
    python3 my_roundtrip.py {input} {output}
"""
from __future__ import annotations

import random
import time
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

from . import ooxml, psd, visual
from .runner import run_command
from .findings import Finding, failures
from .ooxml import Unreadable

ANALYZERS = {
    ".docx": (ooxml.summarize, ooxml.compare),
    ".xlsx": (ooxml.summarize, ooxml.compare),
    ".pptx": (ooxml.summarize, ooxml.compare),
    ".psd": (psd.summarize, psd.compare),
    ".psb": (psd.summarize, psd.compare),
}
MUTATIONS = ("truncate", "bitflip", "zero_block")


@dataclass
class Result:
    file: str
    kind: str
    status: str  # pass | fail | crash | timeout | error | skipped
    findings: list = field(default_factory=list)
    seconds: float = 0.0
    detail: str = ""


@dataclass
class FuzzResult:
    file: str
    kind: str
    mutation: str
    status: str  # ok | crash | timeout


def run_adapter(cmd, src: Path, dst: Path, timeout: float):
    return run_command(cmd, {"input": src, "output": dst}, timeout)


def _renamed(path: Path, tag: str) -> Path:
    return path.with_name(f"{path.stem}.{tag}{path.suffix}")


def round_trip(cmd, src: Path, rel: Path, out_dir: Path, timeout: float, vis=None) -> Result:
    ext = src.suffix.lower()
    start = time.time()
    summarize, compare = ANALYZERS[ext]
    try:
        before = summarize(src)
    except Unreadable as exc:
        return Result(str(rel), ext[1:], "skipped", detail=f"corpus file not analyzable: {exc}")

    dst = out_dir / "roundtrip" / rel
    dst.parent.mkdir(parents=True, exist_ok=True)
    state, detail = run_adapter(cmd, src, dst, timeout)
    if state != "ok":
        return Result(str(rel), ext[1:], state, detail=detail, seconds=time.time() - start)
    if not dst.exists():
        return Result(str(rel), ext[1:], "error", detail="adapter reported success but wrote no output",
                      seconds=time.time() - start)
    try:
        after = summarize(dst)
    except Unreadable as exc:
        return Result(str(rel), ext[1:], "fail", [Finding("reopen", f"saved file is not readable: {exc}")],
                      time.time() - start)

    findings = list(compare(before, after))
    if vis is not None:
        findings.extend(visual.check(vis, src, dst, rel, out_dir, timeout))
    dst2 = _renamed(dst, "second")
    state2, detail2 = run_adapter(cmd, dst, dst2, timeout)
    if state2 != "ok":
        findings.append(Finding("reopen", f"app could not reopen and save its own output ({state2}: {detail2})"))
    else:
        try:
            for f in compare(after, summarize(dst2)):
                findings.append(Finding(f.category, "second save: " + f.message, f.severity))
        except Unreadable as exc:
            findings.append(Finding("reopen", f"second save is not readable: {exc}"))
    status = "fail" if failures(findings) else "pass"
    return Result(str(rel), ext[1:], status, findings, time.time() - start)


def mutate(data: bytes, mode: str, rng: random.Random) -> bytes:
    if len(data) < 2:
        return data
    if mode == "truncate":
        return data[: rng.randrange(1, len(data))]
    buf = bytearray(data)
    if mode == "bitflip":
        for _ in range(rng.randint(1, 8)):
            buf[rng.randrange(len(buf))] ^= 1 << rng.randrange(8)
    else:  # zero_block
        start = rng.randrange(len(buf))
        size = rng.randint(64, 4096)
        buf[start : start + size] = bytes(min(size, len(buf) - start))
    return bytes(buf)


def fuzz_file(cmd, src: Path, rel: Path, out_dir: Path, count: int, seed: int, timeout: float):
    results = []
    data = src.read_bytes()
    rng = random.Random(f"{seed}:{rel}")
    for i in range(count):
        mode = MUTATIONS[i % len(MUTATIONS)]
        mutant = out_dir / "fuzz" / rel.parent / f"{rel.stem}.{i}{rel.suffix}"
        mutant.parent.mkdir(parents=True, exist_ok=True)
        mutant.write_bytes(mutate(data, mode, rng))
        state, _ = run_adapter(cmd, mutant, mutant.with_suffix(".out" + rel.suffix), timeout)
        # Refusing a corrupt file with an error exit is fine; crashing or hanging is not.
        results.append(FuzzResult(str(rel), rel.suffix[1:].lower(), mode, state if state in ("crash", "timeout") else "ok"))
    return results


def corpus_files(corpus: Path):
    for p in sorted(corpus.rglob("*")):
        if p.is_file() and p.suffix.lower() in ANALYZERS:
            yield p, p.relative_to(corpus)


def run(cmd, corpus: Path, out_dir: Path, timeout: float = 60, fuzz: int = 0, seed: int = 0, vis=None):
    out_dir.mkdir(parents=True, exist_ok=True)
    results, fuzzed = [], []
    for src, rel in corpus_files(corpus):
        results.append(round_trip(cmd, src, rel, out_dir, timeout, vis))
        if fuzz:
            fuzzed.extend(fuzz_file(cmd, src, rel, out_dir, fuzz, seed, timeout))
    return results, fuzzed


def summarize_results(results, fuzzed=()):
    kinds = sorted({r.kind for r in results})
    per_kind = {}
    for k in kinds:
        rs = [r for r in results if r.kind == k]
        counts = Counter(r.status for r in rs)
        scored = len(rs) - counts["skipped"]
        cats = Counter(f.category for r in rs for f in failures(r.findings))
        per_kind[k] = {"files": len(rs), "scored": scored, **{s: counts[s] for s in
                       ("pass", "fail", "crash", "timeout", "error", "skipped")},
                       "pass_rate": round(counts["pass"] / scored, 4) if scored else None,
                       "failure_categories": dict(cats.most_common())}
    fz = {}
    for k in sorted({f.kind for f in fuzzed}):
        fs = [f for f in fuzzed if f.kind == k]
        fz[k] = {"mutants": len(fs), "crash": sum(f.status == "crash" for f in fs),
                 "timeout": sum(f.status == "timeout" for f in fs)}
    return {"per_kind": per_kind, "fuzz": fz}


def to_markdown(summary: dict, results, app: str = "app under test") -> str:
    lines = [f"# Parity report: {app}", "", "Structural round-trip checks, plus visual checks only where a `visual` failure category appears below or a renderer was configured.", "",
             "| Type | Files | Scored | Pass | Fail | Crash | Timeout | Error | Skipped | Pass rate |",
             "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |"]
    for k, v in summary["per_kind"].items():
        rate = "n/a" if v["pass_rate"] is None else f"{v['pass_rate'] * 100:.1f}%"
        lines.append(f"| {k} | {v['files']} | {v['scored']} | {v['pass']} | {v['fail']} | {v['crash']} | "
                     f"{v['timeout']} | {v['error']} | {v['skipped']} | {rate} |")
    cats = {}
    for v in summary["per_kind"].values():
        for c, n in v["failure_categories"].items():
            cats[c] = cats.get(c, 0) + n
    if cats:
        lines += ["", "## Failure categories", ""] + [f"- {c}: {n}" for c, n in sorted(cats.items(), key=lambda x: -x[1])]
    if summary["fuzz"]:
        lines += ["", "## Fuzzing (corrupt input handling)", "", "| Type | Mutants | Crashes | Timeouts |", "| --- | --- | --- | --- |"]
        lines += [f"| {k} | {v['mutants']} | {v['crash']} | {v['timeout']} |" for k, v in summary["fuzz"].items()]
    bad = [r for r in results if r.status not in ("pass", "skipped")]
    if bad:
        lines += ["", "## Failing files", ""]
        for r in bad[:50]:
            why = "; ".join(f"[{f.category}] {f.message}" for f in failures(r.findings)) or r.detail
            lines.append(f"- `{r.file}` ({r.status}): {why}")
        if len(bad) > 50:
            lines.append(f"- ... and {len(bad) - 50} more (see the JSON report)")
    return "\n".join(lines) + "\n"
