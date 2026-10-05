from __future__ import annotations

import csv
import hashlib
import re
import sqlite3
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


FIELDNAMES = [
    "post_id",
    "published_date",
    "job_type",
    "seniority",
    "location",
    "hiring_role",
    "company",
    "author_name",
    "author_linkedin",
    "post_url",
    "post_content",
    "email",
    "phone",
    "whatsapp",
    "apply_link",
    "hiring_intent",
    "source",
]


def normalize_url_key(url: str) -> str:
    u = (url or "").strip().lower()
    if not u:
        return ""
    try:
        p = urlparse(u)
        host = (p.netloc or "").replace("www.", "")
        path = re.sub(r"/+$", "", p.path or "")
        return f"{host}{path}"
    except Exception:
        return u


def semantic_key(company: str, title: str, location: str = "") -> str:
    raw = "|".join(
        [
            re.sub(r"\s+", " ", (company or "").lower()).strip(),
            re.sub(r"\s+", " ", (title or "").lower()).strip(),
            re.sub(r"\s+", " ", (location or "").lower()).strip()[:40],
        ]
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]


class SeenStore:
    """Cross-source dedupe by post_id, normalized URL, and company|title|location."""

    def __init__(self, db_path: Path):
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(db_path)
        self.conn.execute(
            "CREATE TABLE IF NOT EXISTS seen_posts (post_id TEXT PRIMARY KEY, seen_at TEXT DEFAULT CURRENT_TIMESTAMP)"
        )
        self.conn.execute(
            "CREATE TABLE IF NOT EXISTS seen_urls (url_key TEXT PRIMARY KEY, seen_at TEXT DEFAULT CURRENT_TIMESTAMP)"
        )
        self.conn.execute(
            "CREATE TABLE IF NOT EXISTS seen_semantic ("
            "sem_key TEXT PRIMARY KEY, seen_at TEXT DEFAULT CURRENT_TIMESTAMP)"
        )
        self.conn.commit()

    def has(self, post_id: str) -> bool:
        row = self.conn.execute("SELECT 1 FROM seen_posts WHERE post_id = ?", (post_id,)).fetchone()
        return row is not None

    def has_any(self, post_id: str, url: str = "", company: str = "", title: str = "", location: str = "") -> bool:
        if post_id and self.has(post_id):
            return True
        uk = normalize_url_key(url)
        if uk:
            row = self.conn.execute("SELECT 1 FROM seen_urls WHERE url_key = ?", (uk,)).fetchone()
            if row:
                return True
        sk = semantic_key(company, title, location)
        if company and title:
            row = self.conn.execute("SELECT 1 FROM seen_semantic WHERE sem_key = ?", (sk,)).fetchone()
            if row:
                return True
        return False

    def add(self, post_id: str, url: str = "", company: str = "", title: str = "", location: str = "") -> None:
        if post_id:
            self.conn.execute("INSERT OR IGNORE INTO seen_posts (post_id) VALUES (?)", (post_id,))
        uk = normalize_url_key(url)
        if uk:
            self.conn.execute("INSERT OR IGNORE INTO seen_urls (url_key) VALUES (?)", (uk,))
        if company and title:
            sk = semantic_key(company, title, location)
            self.conn.execute("INSERT OR IGNORE INTO seen_semantic (sem_key) VALUES (?)", (sk,))
        self.conn.commit()

    def close(self) -> None:
        self.conn.close()


def fingerprint(text: str, url: str = "") -> str:
    raw = f"{url.strip().lower()}|{text.strip().lower()[:500]}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]


def append_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    write_header = not path.exists() or path.stat().st_size == 0
    with path.open("a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES, extrasaction="ignore")
        if write_header:
            writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k, "") for k in FIELDNAMES})


def append_google_sheet(credentials_file: Path, sheet_id: str, worksheet: str, rows: list[dict[str, Any]]) -> None:
    if not rows or not sheet_id:
        return
    if not credentials_file.exists():
        raise FileNotFoundError(
            f"Google credentials not found at {credentials_file}. "
            "Create a service account JSON and share the sheet with that email."
        )
    import gspread
    from google.oauth2.service_account import Credentials

    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]
    creds = Credentials.from_service_account_file(str(credentials_file), scopes=scopes)
    gc = gspread.authorize(creds)
    sh = gc.open_by_key(sheet_id)
    try:
        ws = sh.worksheet(worksheet)
    except gspread.WorksheetNotFound:
        ws = sh.add_worksheet(title=worksheet, rows=1000, cols=len(FIELDNAMES))
        ws.append_row(FIELDNAMES)

    existing = ws.get_all_values()
    if not existing:
        ws.append_row(FIELDNAMES)

    values = [[row.get(k, "") for k in FIELDNAMES] for row in rows]
    ws.append_rows(values, value_input_option="USER_ENTERED")
