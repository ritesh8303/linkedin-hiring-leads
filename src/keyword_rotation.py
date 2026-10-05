"""Rotate keyword lists across scheduled runs to spread API load."""

from __future__ import annotations

from datetime import date


def pick_keywords(keywords: list[str], *, per_run: int, run_index: int | None = None) -> list[str]:
    if not keywords:
        return []
    n = max(1, per_run)
    if len(keywords) <= n:
        return keywords
    idx = run_index if run_index is not None else date.today().toordinal()
    start = (idx * n) % len(keywords)
    out: list[str] = []
    for i in range(n):
        out.append(keywords[(start + i) % len(keywords)])
    return out
