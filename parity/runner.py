"""Run an external command with {placeholder} substitution and classify the outcome."""
from __future__ import annotations

import subprocess


def run_command(cmd, subs: dict, timeout: float):
    argv = [_fill(a, subs) for a in cmd]
    try:
        proc = subprocess.run(argv, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                              stderr=subprocess.PIPE, timeout=timeout)
    except subprocess.TimeoutExpired:
        return "timeout", f"no result after {timeout}s"
    except OSError as exc:
        return "error", str(exc)
    if proc.returncode < 0:
        return "crash", f"killed by signal {-proc.returncode}"
    if proc.returncode != 0:
        tail = proc.stderr.decode("utf-8", "replace").strip().splitlines()[-1:] or [""]
        return "error", f"exit {proc.returncode}: {tail[0]}"
    return "ok", ""


def _fill(arg: str, subs: dict) -> str:
    for key, val in subs.items():
        arg = arg.replace("{" + key + "}", str(val))
    return arg
