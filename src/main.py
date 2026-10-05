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

from .config import load_config, resolve_path
from .enrich import enrich_item
from .providers import fetch_from_providers
from .scheduler_util import seconds_until_next_run
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
    location_policy = str(cfg.get("location_policy") or "")
    require_ai = bool(cfg.get("require_ai"))
    require_data_ai = bool(cfg.get("require_data_ai", True))
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
                location_policy=location_policy,
                search_location=search_location,
                require_ai=require_ai,
                require_data_ai=require_data_ai,
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


def _export_docs_if_enabled(cfg: dict) -> None:
    if not cfg.get("auto_export_docs"):
        return
    try:
        import subprocess

        script = ROOT / "scripts" / "export_docs_jobs.py"
        subprocess.run([sys.executable, str(script)], cwd=str(ROOT), check=False)
    except Exception as exc:  # noqa: BLE001
        console.print(f"[yellow]Docs export skipped:[/] {exc}")


def run_once(*, dry_run: bool = False) -> int:
    cfg = load_config()
    if dry_run:
        console.print("[magenta]Dry run — using sample posts (no network)[/]")
        items = sample_items()
    else:
        items = fetch_from_providers(cfg)

    rows = process_items(items, cfg)
    save_rows(rows, cfg)
    _export_docs_if_enabled(cfg)
    return 0


def run_schedule() -> int:
    cfg = load_config()
    sched = cfg.get("schedule") or {}
    time_str = str(sched.get("time") or cfg.get("schedule_time") or "18:30")
    tz_name = str(sched.get("timezone") or cfg.get("schedule_timezone") or "Europe/Berlin")
    run_immediately = bool(sched.get("run_on_start", True))

    console.print(
        f"[cyan]Daily scheduler[/] — scrape at {time_str} ({tz_name}), "
        f"so jobs are ready before your ~8 PM applications. Ctrl+C to stop."
    )
    if run_immediately:
        run_once(dry_run=False)
    while True:
        secs, nxt = seconds_until_next_run(time_str=time_str, tz_name=tz_name)
        console.print(f"Next run at {nxt.isoformat()} (sleep {int(secs // 60)} min)")
        time.sleep(secs)
        run_once(dry_run=False)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Scrape jobs for your job search (free providers + optional Apify)")
    parser.add_argument("--dry-run", action="store_true", help="Process sample data only")
    parser.add_argument(
        "--schedule",
        action="store_true",
        help="Run daily at schedule.time (default 18:30) before evening applications",
    )
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
