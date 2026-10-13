from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Finding:
    category: str  # structure | text | styles | tables | media | sheets | cells | formulas | slides | geometry | layers | reopen | visual
    message: str
    severity: str = "fail"  # fail | info


def failures(findings) -> list[Finding]:
    return [f for f in findings if f.severity == "fail"]
