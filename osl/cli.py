"""osl-run: show (default) or execute how a file would be launched."""
from __future__ import annotations

import argparse
import hashlib
import os
import subprocess
import sys
from pathlib import Path

from . import recipes as recipe_lib
from .detect import detect_file
from .plan import make_plan
from .runtime import decide, host_arch

DEFAULT_RECIPE_DIRS = (
    "/usr/local/lib/hybrid-os/recipes",
    str(Path(__file__).resolve().parent.parent / "recipes"),
)


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def load_recipes(explicit: str | None) -> list[dict]:
    dirs = [explicit] if explicit else [os.environ.get("OSL_RECIPES", ""), *DEFAULT_RECIPE_DIRS]
    for d in dirs:
        if d and Path(d).is_dir():
            return recipe_lib.load_dir(d)
    return []


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="osl-run", description=__doc__)
    ap.add_argument("file")
    ap.add_argument("--exec", action="store_true", help="actually launch; default is a dry run")
    ap.add_argument(
        "--prefix-root",
        default=os.path.expanduser("~/.local/share/osl/prefixes"),
        help="where per-app Wine prefixes live",
    )
    ap.add_argument("--recipes", help="directory of recipe JSON files")
    args = ap.parse_args(argv)

    path = Path(args.file)
    if not path.is_file():
        print(f"osl-run: not a file: {path}", file=sys.stderr)
        return 1

    info = detect_file(path)
    decision = decide(info, path, host_arch(), Path(args.prefix_root))
    print(f"format : {info.kind} {','.join(info.archs)} {info.detail}".rstrip())
    print(f"runtime: {decision.runtime} ({'supported' if decision.supported else 'unsupported'})")
    print(f"reason : {decision.reason}")
    if not decision.supported:
        return 2
    recipe = recipe_lib.find(load_recipes(args.recipes), sha256=sha256_of(path), filename=path.name)
    if recipe:
        problems = recipe_lib.validate({k: v for k, v in recipe.items() if k != "_file"})
        if problems:
            print("recipe ignored (invalid): " + "; ".join(problems), file=sys.stderr)
            recipe = None
    provisioned = bool(decision.prefix) and (Path(decision.prefix) / ".osl-provisioned").exists()
    plan = make_plan(decision, recipe, provisioned)
    for note in plan.notes:
        print(f"note   : {note}")
    for cmd in plan.setup:
        print("setup  : " + " ".join(cmd))
    print("command: " + " ".join(plan.run))
    if recipe and recipe.get("status") == "broken" and args.exec:
        print("osl-run: recipe says this app is broken; launching anyway", file=sys.stderr)
    if args.exec:
        for cmd in plan.setup:
            subprocess.run(cmd, check=True)
        if decision.prefix and plan.setup:
            Path(decision.prefix).mkdir(parents=True, exist_ok=True)
            (Path(decision.prefix) / ".osl-provisioned").touch()
        os.execvp(plan.run[0], plan.run)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
