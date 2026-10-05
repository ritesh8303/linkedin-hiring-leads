from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from rich.console import Console
from rich.table import Table

from .apify_fetch import build_actor_input, fetch_hiring_posts, list_search_keywords, resolve_actor_id
from .config import load_config, resolve_path
from .enrich import enrich_item
from .storage import SeenStore, append_csv, append_google_sheet

console = Console()
ROOT = Path(__file__).resolve().parents[1]


def sample_items() -> list[dict]:
    sample_path = ROOT / "data" / "sample_posts.json"
    with sample_path.open(encoding="utf-8") as f:
        return json.load(f)


def process_items(items: list[dict], cfg: dict) -> list[dict]:
    roles = cfg.get("job_roles") or []
    keywords = cfg.get("keywords") or []
    mode = (cfg.get("mode") or "jobs").lower()
    entry_level_only = bool(cfg.get("entry_level_only"))
    require_germany = bool(cfg.get("require_germany"))
    require_ai = bool(cfg.get("require_ai", True if entry_level_only else False))
    search_location = str(cfg.get("location") or "")
    seen_path = resolve_path(cfg["output"]["sqlite_path"])
    store = SeenStore(seen_path)
    run_fps: set[str] = set()
    qualified: list[dict] = []
    stats = {"raw": len(items), "dup": 0, "filtered": 0, "saved": 0}

    try:
        for item in items:
            row = enrich_item(
                item,
                roles,
                keywords,
                mode=mode,
                entry_level_only=entry_level_only,
                require_germany=require_germany,
                search_location=search_location,
                require_ai=require_ai,
            )
            if row is None:
                stats["filtered"] += 1
                continue
            pid = row["post_id"]
            if pid in run_fps or store.has(pid):
                stats["dup"] += 1
                continue
            run_fps.add(pid)
            store.add(pid)
            qualified.append(row)
            stats["saved"] += 1
    finally:
        store.close()

    console.print(
        f"[cyan]raw={stats['raw']}[/] filtered={stats['filtered']} "
        f"dupes={stats['dup']} [green]saved={stats['saved']}[/]"
    )
    return qualified


def save_rows(rows: list[dict], cfg: dict) -> None:
    if not rows:
        console.print("[yellow]No new qualified jobs this run.[/]")
        return

    csv_path = resolve_path(cfg["output"]["csv_path"])
    append_csv(csv_path, rows)
    console.print(f"[green]Saved {len(rows)} row(s) -> {csv_path}[/]")

    sheet_id = (cfg.get("output") or {}).get("google_sheet_id") or ""
    if sheet_id:
        creds = resolve_path(cfg["output"].get("google_credentials_file") or "credentials/google-service-account.json")
        append_google_sheet(creds, sheet_id, cfg["output"].get("google_worksheet") or "Leads", rows)
        console.print(f"[green]Appended {len(rows)} row(s) -> Google Sheet {sheet_id}[/]")

    table = Table(title="New qualified jobs")
    for col in ("company", "hiring_role", "seniority", "location", "job_type"):
        table.add_column(col)
    for r in rows[:30]:
        table.add_row(
            str(r.get("company") or "")[:28],
            str(r.get("hiring_role") or "")[:32],
            str(r.get("seniority") or "")[:16],
            str(r.get("location") or "")[:22],
            str(r.get("job_type") or ""),
        )
    console.print(table)
    if len(rows) > 30:
        console.print(f"... and {len(rows) - 30} more (see CSV)")


def fetch_all_items(cfg: dict) -> list[dict]:
    actor = resolve_actor_id(cfg)
    mode = (cfg.get("mode") or "jobs").lower()
    console.print(f"[cyan]Running Apify actor[/] {actor} (mode={mode})")

    if mode != "jobs":
        run_input = build_actor_input(cfg)
        console.print(f"Roles: {', '.join(cfg.get('job_roles') or [])}")
        return fetch_hiring_posts(cfg["apify_token"], actor, run_input)

    keywords = list_search_keywords(cfg)
    location = cfg.get("location") or "Remote"
    console.print(f"Location: {location}")
    console.print(f"Keywords ({len(keywords)}): {', '.join(keywords)}")

    all_items: list[dict] = []
    seen_ids: set[str] = set()
    for kw in keywords:
        console.print(f"[magenta]Search:[/] {kw}")
        run_input = build_actor_input(cfg, keyword=kw)
        items = fetch_hiring_posts(cfg["apify_token"], actor, run_input)
        added = 0
        for item in items:
            jid = str(item.get("jobId") or item.get("jobUrl") or item.get("url") or "")
            if jid and jid in seen_ids:
                continue
            if jid:
                seen_ids.add(jid)
            item.setdefault("searchKeywords", kw)
            item.setdefault("searchLocation", location)
            all_items.append(item)
            added += 1
        console.print(f"  got {len(items)} raw, +{added} unique (total {len(all_items)})")
    return all_items


def run_once(*, dry_run: bool = False) -> int:
    cfg = load_config()
    if dry_run:
        console.print("[magenta]Dry run — using sample posts (no Apify credits)[/]")
        items = sample_items()
    else:
        items = fetch_all_items(cfg)

    rows = process_items(items, cfg)
    save_rows(rows, cfg)
    return 0


def run_schedule() -> int:
    cfg = load_config()
    hours = float(cfg.get("schedule_hours") or 6)
    console.print(f"[cyan]Scheduler started — every {hours} hour(s). Ctrl+C to stop.[/]")
    run_once(dry_run=False)
    while True:
        console.print(f"Sleeping {hours}h...")
        time.sleep(hours * 3600)
        run_once(dry_run=False)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Scrape LinkedIn jobs for your job search")
    parser.add_argument("--dry-run", action="store_true", help="Process sample data only (no Apify)")
    parser.add_argument("--schedule", action="store_true", help="Re-run every schedule_hours from config")
    args = parser.parse_args(argv)

    try:
        if args.schedule:
            if args.dry_run:
                console.print("[red]--schedule cannot be combined with --dry-run[/]")
                return 2
            return run_schedule()
        return run_once(dry_run=args.dry_run)
    except KeyboardInterrupt:
        console.print("\nStopped.")
        return 130
    except Exception as exc:  # noqa: BLE001
        console.print(f"[red]Error:[/] {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
