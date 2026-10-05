"""Export job CSV snapshot to docs/jobs.json for GitHub Pages."""

from __future__ import annotations

import csv
import json
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.config import load_config, resolve_path

OUT_PATH = ROOT / "docs" / "jobs.json"


def main() -> None:
    cfg = load_config()
    csv_path = resolve_path(cfg["output"]["csv_path"])
    if not csv_path.exists():
        print(f"No CSV yet at {csv_path}")
        return

    with csv_path.open(encoding="utf-8", newline="") as f:
        records = list(csv.DictReader(f))

    out = []
    for r in records:
        out.append(
            {
                "id": r.get("post_id") or "",
                "title": r.get("hiring_role") or "",
                "company": r.get("company") or "",
                "location": r.get("location") or "",
                "seniority": r.get("seniority") or "",
                "job_type": r.get("job_type") or "",
                "published": r.get("published_date") or "",
                "url": r.get("post_url") or r.get("apply_link") or "",
                "apply": r.get("apply_link") or r.get("post_url") or "",
                "employment": r.get("hiring_intent") or "",
                "email": r.get("email") or "",
                "source": r.get("source") or "",
                "description": (r.get("post_content") or "")[:1800],
            }
        )

    payload = {"updated": date.today().isoformat(), "count": len(out), "jobs": out}
    OUT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {len(out)} jobs -> {OUT_PATH}")


if __name__ == "__main__":
    main()
