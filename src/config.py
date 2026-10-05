from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]


def load_config(path: Path | None = None) -> dict[str, Any]:
    load_dotenv(ROOT / ".env")
    cfg_path = path or ROOT / "config.yaml"
    with cfg_path.open(encoding="utf-8") as f:
        cfg = yaml.safe_load(f) or {}

    sheet_id = os.getenv("GOOGLE_SHEET_ID") or cfg.get("output", {}).get("google_sheet_id", "")
    cfg.setdefault("output", {})
    cfg["output"]["google_sheet_id"] = sheet_id or ""
    cfg["apify_token"] = os.getenv("APIFY_API_TOKEN") or os.getenv("APIFY_TOKEN") or ""
    return cfg


def resolve_path(relative: str) -> Path:
    p = Path(relative)
    return p if p.is_absolute() else ROOT / p
