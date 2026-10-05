"""Multi-provider job fetch (LinkedIn guest + SerpAPI + Apify with monthly budget)."""

from __future__ import annotations

from datetime import date
from typing import Any

from rich.console import Console

from .apify_budget import record_jobs, remaining_jobs
from .apify_fetch import build_actor_input, fetch_hiring_posts, list_search_keywords, resolve_actor_id
from .keyword_rotation import pick_keywords
from .linkedin_guest import fetch_linkedin_guest_jobs
from .progress import EventCallback, emit
from .serpapi_jobs import fetch_google_jobs

console = Console()


def _dedupe_key(item: dict[str, Any]) -> str:
    return str(
        item.get("jobId")
        or item.get("jobUrl")
        or item.get("url")
        or item.get("share_link")
        or f"{item.get('title')}|{item.get('company')}|{item.get('location')}"
    )


def merge_unique(existing: list[dict[str, Any]], new_items: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], int]:
    seen = {_dedupe_key(x) for x in existing if _dedupe_key(x)}
    added = 0
    for item in new_items:
        key = _dedupe_key(item)
        if key and key in seen:
            continue
        if key:
            seen.add(key)
        existing.append(item)
        added += 1
    return existing, added


def _search_plans(cfg: dict[str, Any]) -> list[dict[str, Any]]:
    plans = cfg.get("search_plans")
    if plans:
        return list(plans)

    policy = (cfg.get("location_policy") or "").strip().lower()
    keywords = list_search_keywords(cfg)

    if policy in {"remote_world_eu_local", "remote_worldwide_eu_hybrid_onsite"}:
        remote_locs = cfg.get("remote_search_locations") or ["Remote"]
        eu_locs = cfg.get("eu_search_locations") or [
            "Germany",
            "Netherlands",
            "France",
            "Spain",
            "Ireland",
            "Poland",
            "Portugal",
            "Belgium",
            "Austria",
            "Italy",
            "Sweden",
            "Denmark",
        ]
        eu_kws = keywords
        out: list[dict[str, Any]] = []
        for loc in remote_locs:
            out.append(
                {
                    "label": f"Remote worldwide @ {loc}",
                    "location": loc,
                    "keywords": keywords,
                    "workplace_types": ["remote"],
                }
            )
        for loc in eu_locs:
            out.append(
                {
                    "label": f"EU hybrid/onsite @ {loc}",
                    "location": loc,
                    "keywords": eu_kws,
                    "workplace_types": ["hybrid", "on-site"],
                }
            )
        return out

    return [
        {
            "label": f"All @ {cfg.get('location') or 'Remote'}",
            "location": cfg.get("location") or "Remote",
            "keywords": keywords,
            "workplace_types": [],
        }
    ]


def _plans_for_run(plans: list[dict[str, Any]], cfg: dict[str, Any]) -> list[dict[str, Any]]:
    remote = [p for p in plans if p.get("workplace_types") == ["remote"]]
    eu = [p for p in plans if p not in remote]
    n_eu = int(cfg.get("eu_countries_per_run") or 4)
    idx = date.today().toordinal()
    eu_pick: list[dict[str, Any]] = []
    if eu:
        for i in range(min(n_eu, len(eu))):
            eu_pick.append(eu[(idx + i) % len(eu)])
    return (remote[:1] if remote else []) + eu_pick


def fetch_from_providers(
    cfg: dict[str, Any],
    on_event: EventCallback | None = None,
) -> list[dict[str, Any]]:
    providers = cfg.get("providers") or ["linkedin_guest", "serpapi"]
    if isinstance(providers, str):
        providers = [providers]

    max_results = int(cfg.get("max_results") or 25)
    date_posted = cfg.get("date_posted") or "pastMonth"
    entry_level_only = bool(cfg.get("entry_level_only"))
    fetch_details = bool(cfg.get("linkedin_fetch_details", True))
    delay = float(cfg.get("linkedin_delay_sec") or 1.5)
    run_idx = date.today().toordinal()

    all_plans = _search_plans(cfg)
    plans = _plans_for_run(all_plans, cfg)

    serp_all = cfg.get("serpapi_keywords") or list_search_keywords(cfg)
    serp_keywords = pick_keywords(
        serp_all,
        per_run=int(cfg.get("serpapi_keywords_per_run") or cfg.get("serpapi_max_keywords") or 5),
        run_index=run_idx,
    )

    li_remote_k = int(cfg.get("linkedin_remote_keywords_per_run") or 6)
    li_eu_k = int(cfg.get("linkedin_eu_keywords_per_run") or cfg.get("eu_max_keywords") or 4)

    console.print(f"[cyan]Providers:[/] {', '.join(providers)}")
    console.print(f"Search plans this run: {len(plans)} (of {len(all_plans)} total)")
    emit(
        on_event,
        "providers",
        f"Providers: {', '.join(providers)} — {len(plans)} search plan(s)",
        providers=providers,
        plans=len(plans),
    )

    all_items: list[dict[str, Any]] = []

    for provider in providers:
        name = str(provider).strip().lower()
        if name in {"linkedin_guest", "linkedin", "guest"}:
            console.print("[magenta]LinkedIn guest[/]")
            emit(on_event, "linkedin_guest", "Starting LinkedIn guest searches…")
            for plan in plans:
                loc = plan.get("location") or "Remote"
                wtypes = plan.get("workplace_types") or []
                full_kws = plan.get("keywords") or list_search_keywords(cfg)
                per = li_remote_k if wtypes == ["remote"] else li_eu_k
                kws = pick_keywords(full_kws, per_run=per, run_index=run_idx)
                console.print(f"  Plan: {plan.get('label') or loc} ({len(kws)} keywords)")
                emit(on_event, "linkedin_guest", f"Plan: {plan.get('label') or loc} ({len(kws)} keywords)")
                for kw in kws:
                    console.print(f"    Search: {kw}")
                    emit(on_event, "linkedin_guest", f"Search: {kw} @ {loc}")
                    try:
                        items = fetch_linkedin_guest_jobs(
                            keywords=kw,
                            location=loc,
                            max_results=max_results,
                            date_posted=date_posted,
                            entry_level_only=entry_level_only,
                            fetch_details=fetch_details,
                            delay_sec=delay,
                            workplace_types=list(wtypes),
                        )
                    except Exception as exc:  # noqa: BLE001
                        console.print(f"    [yellow]LinkedIn guest failed:[/] {exc}")
                        emit(on_event, "warning", f"LinkedIn guest failed: {exc}")
                        continue
                    for item in items:
                        item.setdefault("searchKeywords", kw)
                        item.setdefault("searchLocation", loc)
                        if wtypes and not item.get("workplaceType"):
                            item["workplaceType"] = " ".join(wtypes)
                    all_items, added = merge_unique(all_items, items)
                    console.print(f"    got {len(items)} raw, +{added} unique (total {len(all_items)})")
                    emit(
                        on_event,
                        "linkedin_guest",
                        f"got {len(items)} raw, +{added} unique (total {len(all_items)})",
                        total=len(all_items),
                    )

        elif name in {"serpapi", "google_jobs", "serpapi_google_jobs"}:
            token = cfg.get("serpapi_key") or ""
            if not token:
                console.print("[yellow]Skipping SerpAPI — set SERPAPI_API_KEY in .env[/]")
                emit(on_event, "warning", "Skipping SerpAPI — set SERPAPI_API_KEY in .env")
                continue
            console.print(f"[magenta]SerpAPI Google Jobs[/] — {len(serp_keywords)} keyword(s)")
            emit(on_event, "serpapi", f"Starting SerpAPI — {len(serp_keywords)} keyword(s)")
            chips = cfg.get("serpapi_chips")
            serp_locs = cfg.get("serpapi_locations") or ["Remote", "Berlin, Germany", "Amsterdam, Netherlands"]
            serp_locs = serp_locs[: int(cfg.get("serpapi_locations_per_run") or 3)]
            for loc in serp_locs:
                for kw in serp_keywords:
                    q = kw
                    if str(loc).lower() == "remote" and "remote" not in q.lower():
                        q = f"{q} remote"
                    console.print(f"  Search: {q} @ {loc}")
                    emit(on_event, "serpapi", f"Search: {q} @ {loc}")
                    try:
                        items = fetch_google_jobs(
                            api_key=token,
                            keywords=q,
                            location=loc,
                            max_results=min(max_results, int(cfg.get("serpapi_max_results") or 15)),
                            chips=chips,
                        )
                    except Exception as exc:  # noqa: BLE001
                        console.print(f"  [yellow]SerpAPI failed:[/] {exc}")
                        emit(on_event, "warning", f"SerpAPI failed: {exc}")
                        continue
                    for item in items:
                        item.setdefault("searchKeywords", q)
                        item.setdefault("searchLocation", loc)
                    all_items, added = merge_unique(all_items, items)
                    console.print(f"  got {len(items)} raw, +{added} unique (total {len(all_items)})")
                    emit(
                        on_event,
                        "serpapi",
                        f"got {len(items)} raw, +{added} unique (total {len(all_items)})",
                        total=len(all_items),
                    )

        elif name == "apify":
            if not cfg.get("apify_token"):
                console.print("[yellow]Skipping Apify — set APIFY_API_TOKEN in .env[/]")
                emit(on_event, "warning", "Skipping Apify — set APIFY_API_TOKEN in .env")
                continue
            left = remaining_jobs(cfg)
            if left <= 0:
                console.print("[yellow]Apify monthly job budget exhausted — skipping until next month[/]")
                emit(on_event, "warning", "Apify monthly job budget exhausted — skipping until next month")
                continue
            per_search = min(
                int(cfg.get("apify_max_jobs_per_search") or 20),
                left,
            )
            searches = int(cfg.get("apify_searches_per_run") or 2)
            console.print(f"[magenta]Apify[/] budget left ~{left} jobs; {searches} search(es) x {per_search} jobs")
            emit(
                on_event,
                "apify",
                f"Apify budget left ~{left} jobs; {searches} search(es) × {per_search}",
            )
            actor = resolve_actor_id(cfg)
            apify_plans = plans[:1] + [p for p in plans if p.get("workplace_types") != ["remote"]][:1]
            apify_kws = pick_keywords(
                list_search_keywords(cfg),
                per_run=searches,
                run_index=run_idx + 1,
            )
            used_this_run = 0
            for plan in apify_plans:
                if used_this_run >= left:
                    break
                loc = plan.get("location") or "Remote"
                for kw in apify_kws:
                    if used_this_run >= left:
                        break
                    cap = min(per_search, left - used_this_run)
                    console.print(f"  Search: {kw} @ {loc} (max {cap})")
                    emit(on_event, "apify", f"Search: {kw} @ {loc} (max {cap})")
                    run_input = build_actor_input(cfg, keyword=kw)
                    run_input["location"] = loc
                    run_input["maxItems"] = cap
                    try:
                        items = fetch_hiring_posts(cfg["apify_token"], actor, run_input)
                    except Exception as exc:  # noqa: BLE001
                        console.print(f"  [yellow]Apify failed:[/] {exc}")
                        emit(on_event, "warning", f"Apify failed: {exc}")
                        continue
                    used_this_run += len(items)
                    record_jobs(len(items), cfg)
                    for item in items:
                        item.setdefault("searchKeywords", kw)
                        item.setdefault("searchLocation", loc)
                        item.setdefault("source", "apify")
                    all_items, added = merge_unique(all_items, items)
                    console.print(f"  got {len(items)} raw, +{added} unique (total {len(all_items)})")
                    emit(
                        on_event,
                        "apify",
                        f"got {len(items)} raw, +{added} unique (total {len(all_items)})",
                        total=len(all_items),
                    )
            console.print(f"  Apify used {used_this_run} jobs this run; ~{remaining_jobs(cfg)} left this month")
            emit(
                on_event,
                "apify",
                f"Apify used {used_this_run} jobs this run; ~{remaining_jobs(cfg)} left this month",
            )

        else:
            console.print(f"[yellow]Unknown provider skipped:[/] {provider}")
            emit(on_event, "warning", f"Unknown provider skipped: {provider}")

    emit(on_event, "fetch_done", f"Fetch complete — {len(all_items)} unique raw listings", total=len(all_items))
    return all_items
