"""Per-app compatibility recipes: validation and lookup.

A recipe records settings that made an app work, plus the evidence for it.
Recipes are data; the OS base never needs patching to add one.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

RUNTIMES = {"native", "wine", "darling"}
STATUSES = {"untested", "works", "partial", "broken"}
MATCH_KEYS = {"sha256", "filename"}

# Recipes are data from contributors, so what they may set is deliberately narrow.
ENV_KEY = re.compile(r"^[A-Z_][A-Z0-9_]*$")
VERB = re.compile(r"^[a-z0-9_.-]+$")
DLL = re.compile(r"^[A-Za-z0-9_.*-]+$")
MODE = re.compile(r"^(n|b|native|builtin|)(,(n|b|native|builtin))*$")
WINE_ARCHES = {"win32", "win64"}
FORBIDDEN_ENV = {
    "LD_PRELOAD", "LD_LIBRARY_PATH", "PATH", "HOME", "WINEPREFIX", "WINEARCH",
    "WINEDLLOVERRIDES", "WINELOADER", "WINESERVER",
}


def validate_wine(cfg) -> list[str]:
    if not isinstance(cfg, dict):
        return ["wine must be an object"]
    errors = []
    if "arch" in cfg and cfg["arch"] not in WINE_ARCHES:
        errors.append(f"wine.arch must be one of {sorted(WINE_ARCHES)}")
    for dll, mode in (cfg.get("dll_overrides") or {}).items():
        if not DLL.match(str(dll)) or not isinstance(mode, str) or not MODE.match(mode):
            errors.append(f"bad dll override: {dll!r}={mode!r}")
    for key, val in (cfg.get("env") or {}).items():
        if not ENV_KEY.match(str(key)) or key in FORBIDDEN_ENV:
            errors.append(f"environment variable not allowed in recipes: {key!r}")
        if not isinstance(val, str) or "\n" in val or "\0" in val:
            errors.append(f"bad value for environment variable {key!r}")
    for verb in cfg.get("winetricks") or []:
        if not isinstance(verb, str) or not VERB.match(verb):
            errors.append(f"bad winetricks verb: {verb!r}")
    return errors


def validate(recipe: dict) -> list[str]:
    errors = []
    for key in ("id", "name", "runtime", "status", "match"):
        if key not in recipe:
            errors.append(f"missing required field: {key}")
    if "runtime" in recipe and recipe["runtime"] not in RUNTIMES:
        errors.append(f"runtime must be one of {sorted(RUNTIMES)}")
    if "status" in recipe and recipe["status"] not in STATUSES:
        errors.append(f"status must be one of {sorted(STATUSES)}")
    match = recipe.get("match")
    if isinstance(match, dict):
        if not (set(match) & MATCH_KEYS):
            errors.append("match needs at least one of: " + ", ".join(sorted(MATCH_KEYS)))
    elif "match" in recipe:
        errors.append("match must be an object")
    if "wine" in recipe:
        errors.extend(validate_wine(recipe["wine"]))
    if recipe.get("status") in {"works", "partial"} and not recipe.get("evidence"):
        errors.append("status works/partial requires at least one evidence entry (test run or log link)")
    return errors


def load_dir(directory) -> list[dict]:
    out = []
    for p in sorted(Path(directory).glob("*.json")):
        data = json.loads(p.read_text())
        data["_file"] = p.name
        out.append(data)
    return out


def find(recipes, sha256=None, filename=None):
    for r in recipes:
        m = r.get("match", {})
        if sha256 and m.get("sha256") == sha256:
            return r
        if filename and m.get("filename") == filename:
            return r
    return None


def main(argv=None) -> int:
    paths = list(argv if argv is not None else sys.argv[1:])
    bad = 0
    for p in paths:
        errs = validate(json.loads(Path(p).read_text()))
        for e in errs:
            print(f"{p}: {e}")
        bad += bool(errs)
    print("ok" if not bad else f"{bad} file(s) invalid")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
