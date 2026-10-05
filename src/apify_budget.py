"""Track Apify job extractions against a monthly credit budget (~$5/month)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PATH = ROOT / "data" / "apify_budget.json"


def _month_key(when: datetime | None = None) -> str:
    dt = when or datetime.now(timezone.utc)
    return dt.strftime("%Y-%m")


def load_budget(path: Path | None = None) -> dict[str, Any]:
    p = path or DEFAULT_PATH
    if not p.exists():
        return {"month": _month_key(), "jobs_used": 0}
    data = json.loads(p.read_text(encoding="utf-8"))
    if data.get("month") != _month_key():
        return {"month": _month_key(), "jobs_used": 0}
    return data


def save_budget(data: dict[str, Any], path: Path | None = None) -> None:
    p = path or DEFAULT_PATH
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, indent=2), encoding="utf-8")


def remaining_jobs(cfg: dict[str, Any]) -> int:
    cap = int(cfg.get("apify_monthly_job_budget") or 450)
    used = int(load_budget().get("jobs_used") or 0)
    return max(0, cap - used)


def record_jobs(count: int, cfg: dict[str, Any]) -> int:
    if count <= 0:
        return remaining_jobs(cfg)
    data = load_budget()
    data["jobs_used"] = int(data.get("jobs_used") or 0) + count
    data["month"] = _month_key()
    save_budget(data)
    return remaining_jobs(cfg)
