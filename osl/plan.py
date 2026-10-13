"""Turn a runtime decision plus an optional recipe into setup and run commands."""
from __future__ import annotations

from dataclasses import dataclass

from .runtime import Decision


@dataclass(frozen=True)
class Plan:
    setup: tuple[tuple[str, ...], ...]  # run once, in order, before the first launch
    run: tuple[str, ...]
    notes: tuple[str, ...] = ()


def _status_note(recipe: dict) -> str:
    status = recipe.get("status", "untested")
    text = f"recipe {recipe.get('id', '?')}: {status}"
    if status == "untested":
        text += " (no evidence yet that this app works)"
    if recipe.get("notes") and status in {"partial", "broken"}:
        text += f" - {recipe['notes']}"
    return text


def make_plan(decision: Decision, recipe: dict | None, provisioned: bool) -> Plan:
    notes = (_status_note(recipe),) if recipe else ()
    if decision.runtime != "wine":
        return Plan((), decision.command, notes)

    cfg = (recipe or {}).get("wine") or {}
    target = decision.command[-1]
    base_env = [f"WINEPREFIX={decision.prefix}"]

    run_env = list(base_env)
    overrides = cfg.get("dll_overrides") or {}
    if overrides:
        run_env.append("WINEDLLOVERRIDES=" + ";".join(f"{d}={m}" for d, m in sorted(overrides.items())))
    for key, val in sorted((cfg.get("env") or {}).items()):
        run_env.append(f"{key}={val}")

    setup: list[tuple[str, ...]] = []
    if not provisioned:
        init_env = list(base_env)
        if cfg.get("arch"):
            init_env.append(f"WINEARCH={cfg['arch']}")
        setup.append(("env", *init_env, "wineboot", "--init"))
        verbs = cfg.get("winetricks") or []
        if verbs:
            setup.append(("env", *base_env, "winetricks", "-q", *verbs))
    if recipe is None:
        notes = ("no recipe for this file; using Wine defaults",)
    return Plan(tuple(setup), ("env", *run_env, "wine", target), notes)
