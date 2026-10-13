"""Structural summaries and comparison for DOCX, XLSX, and PPTX files (standard library only).

Untrusted input: members are size-limited and the archive is integrity-checked before parsing.
"""
from __future__ import annotations

import re
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path

from .findings import Finding

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
A = "{http://schemas.openxmlformats.org/drawingml/2006/main}"
S = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"

VOLATILE = {"docProps/core.xml", "docProps/app.xml"}  # rewritten by every save
REQUIRED = {"docx": "word/document.xml", "xlsx": "xl/workbook.xml", "pptx": "ppt/presentation.xml"}
MAX_PART_BYTES = 64 << 20
MAX_PARTS = 20000


class Unreadable(Exception):
    pass


def kind_of(path) -> str:
    ext = Path(path).suffix.lower().lstrip(".")
    if ext not in REQUIRED:
        raise Unreadable(f"unsupported extension: .{ext}")
    return ext


def _num(name: str) -> int:
    m = re.search(r"(\d+)\.xml$", name)
    return int(m.group(1)) if m else 0


def _xml(z: zipfile.ZipFile, name: str):
    info = z.getinfo(name)
    if info.file_size > MAX_PART_BYTES:
        raise Unreadable(f"{name} too large to analyze")
    try:
        return ET.fromstring(z.read(name))
    except ET.ParseError as exc:
        raise Unreadable(f"{name}: invalid XML ({exc})") from exc


def _text(el, tag) -> str:
    return "".join(t.text or "" for t in el.iter(tag))


def summarize(path) -> dict:
    kind = kind_of(path)
    try:
        z = zipfile.ZipFile(path)
    except (zipfile.BadZipFile, OSError) as exc:
        raise Unreadable(f"not a readable zip: {exc}") from exc
    with z:
        infos = [i for i in z.infolist() if not i.is_dir()]
        if len(infos) > MAX_PARTS:
            raise Unreadable("too many parts")
        if z.testzip() is not None:
            raise Unreadable("corrupt zip member")
        names = sorted(i.filename for i in infos)
        summary = {
            "kind": kind,
            "parts": [n for n in names if n not in VOLATILE],
            "media": sum(1 for n in names if "/media/" in n),
        }
        if REQUIRED[kind] not in names:
            summary["missing_required"] = True
            return summary
        summary["missing_required"] = False
        {"docx": _docx, "xlsx": _xlsx, "pptx": _pptx}[kind](z, names, summary)
        return summary


def _docx(z, names, s):
    root = _xml(z, "word/document.xml")
    paras = [_text(p, W + "t") for p in root.iter(W + "p")]
    s["paragraphs"] = [p for p in paras if p.strip()]
    s["tables"] = sum(1 for _ in root.iter(W + "tbl"))
    s["drawings"] = sum(1 for _ in root.iter(W + "drawing"))
    s["styles"] = []
    if "word/styles.xml" in names:
        s["styles"] = sorted(st.get(W + "styleId", "") for st in _xml(z, "word/styles.xml").iter(W + "style"))


def _xlsx(z, names, s):
    wb = _xml(z, "xl/workbook.xml")
    s["sheets"] = [sh.get("name", "") for sh in wb.iter(S + "sheet")]
    sheet_files = sorted((n for n in names if re.match(r"xl/worksheets/[^/]+\.xml$", n)), key=_num)
    cells, formulas = [], []
    for n in sheet_files:
        root = _xml(z, n)
        cells.append(sum(1 for c in root.iter(S + "c") if c.find(S + "v") is not None or c.find(S + "is") is not None))
        formulas.append(sum(1 for _ in root.iter(S + "f")))
    s["cells"], s["formulas"] = cells, formulas
    s["strings"] = []
    if "xl/sharedStrings.xml" in names:
        s["strings"] = sorted(_text(si, S + "t") for si in _xml(z, "xl/sharedStrings.xml").iter(S + "si"))


def _pptx(z, names, s):
    slide_files = sorted((n for n in names if re.match(r"ppt/slides/slide\d+\.xml$", n)), key=_num)
    s["slides"] = [[t.text or "" for t in _xml(z, n).iter(A + "t")] for n in slide_files]


def compare(before: dict, after: dict) -> list[Finding]:
    out: list[Finding] = []
    if before["kind"] != after["kind"]:
        return [Finding("structure", f"file type changed: {before['kind']} -> {after['kind']}")]
    if after.get("missing_required"):
        return [Finding("structure", f"required part missing: {REQUIRED[after['kind']]}")]
    dropped = sorted(set(before["parts"]) - set(after["parts"]))
    if dropped:
        out.append(Finding("structure", f"{len(dropped)} part(s) not present after save (apps may rename parts)", "info"))
    if after["media"] < before["media"]:
        out.append(Finding("media", f"media files dropped: {before['media']} -> {after['media']}"))

    kind = before["kind"]
    if kind == "docx":
        a, b = before["paragraphs"], after["paragraphs"]
        if a != b:
            first = next((i for i, (x, y) in enumerate(zip(a, b)) if x != y), min(len(a), len(b)))
            out.append(Finding("text", f"paragraphs {len(a)} -> {len(b)}; first difference at paragraph {first + 1}"))
        for key, label in (("tables", "tables"), ("drawings", "drawings")):
            if after[key] < before[key]:
                out.append(Finding("tables" if key == "tables" else "media", f"{label} dropped: {before[key]} -> {after[key]}"))
        lost = sorted(set(before["styles"]) - set(after["styles"]))
        if lost:
            out.append(Finding("styles", f"style definitions lost: {', '.join(lost[:5])}"))
    elif kind == "xlsx":
        if before["sheets"] != after["sheets"]:
            out.append(Finding("sheets", f"sheets {before['sheets']} -> {after['sheets']}"))
        if before["cells"] != after["cells"]:
            out.append(Finding("cells", f"cell counts per sheet {before['cells']} -> {after['cells']}"))
        if before["formulas"] != after["formulas"]:
            out.append(Finding("formulas", f"formula counts per sheet {before['formulas']} -> {after['formulas']}"))
        missing = sorted(set(before["strings"]) - set(after["strings"]))
        if missing:
            out.append(Finding("text", f"{len(missing)} shared string(s) lost"))
    elif kind == "pptx":
        if len(before["slides"]) != len(after["slides"]):
            out.append(Finding("slides", f"slide count {len(before['slides'])} -> {len(after['slides'])}"))
        else:
            for i, (x, y) in enumerate(zip(before["slides"], after["slides"]), 1):
                if x != y:
                    out.append(Finding("text", f"text differs on slide {i}"))
                    break
    return out
