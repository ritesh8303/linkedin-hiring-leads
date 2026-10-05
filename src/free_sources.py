"""Free public job sources: Arbeitnow, Himalayas, Remotive, BA Jobsuche, ATS boards."""

from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import requests
import yaml

from .progress import EventCallback, emit

ROOT = Path(__file__).resolve().parents[1]
UA = "PersonalJobRadar/1.0 (+https://github.com/ritesh8303/linkedin-hiring-leads; local research)"


def _norm_item(
    *,
    title: str,
    company: str,
    location: str,
    url: str,
    description: str = "",
    source: str,
    job_id: str = "",
    workplace: str = "",
    remote: bool | None = None,
) -> dict[str, Any]:
    jid = job_id or hashlib.sha256(f"{source}|{company}|{title}|{url}".encode()).hexdigest()[:20]
    if remote is True and not workplace:
        workplace = "remote"
    return {
        "jobId": f"{source}:{jid}",
        "title": title.strip(),
        "companyName": company.strip(),
        "location": location.strip(),
        "jobUrl": url.strip(),
        "url": url.strip(),
        "description": (description or "")[:8000],
        "source": source,
        "workplaceType": workplace,
    }


def _title_matches(title: str, keywords: list[str]) -> bool:
    hay = (title or "").lower()
    if not keywords:
        return True
    return any(k.lower() in hay for k in keywords if k)


def fetch_arbeitnow(cfg: dict[str, Any], on_event: EventCallback | None = None) -> list[dict[str, Any]]:
    max_pages = int(cfg.get("arbeitnow_max_pages") or 3)
    keywords = list(cfg.get("job_roles") or cfg.get("search_keywords") or [])
    out: list[dict[str, Any]] = []
    headers = {"User-Agent": UA, "Accept": "application/json"}
    emit(on_event, "arbeitnow", f"Arbeitnow — up to {max_pages} page(s)")
    for page in range(1, max_pages + 1):
        try:
            resp = requests.get(
                "https://www.arbeitnow.com/api/job-board-api",
                params={"page": page},
                headers=headers,
                timeout=25,
            )
            resp.raise_for_status()
            jobs = (resp.json() or {}).get("data") or []
        except Exception as exc:  # noqa: BLE001
            emit(on_event, "warning", f"Arbeitnow page {page} failed: {exc}")
            break
        if not jobs:
            break
        for j in jobs:
            title = str(j.get("title") or "")
            if keywords and not _title_matches(title, keywords[:40]):
                # soft gate: also keep if tags mention data/ai
                tags = " ".join(str(t) for t in (j.get("tags") or [])).lower()
                if not re.search(r"\b(data|ai|ml|analytics|cloud|aws|python)\b", f"{title} {tags}".lower()):
                    continue
            loc = str(j.get("location") or "")
            remote = bool(j.get("remote"))
            out.append(
                _norm_item(
                    title=title,
                    company=str(j.get("company_name") or j.get("company") or ""),
                    location="Remote" if remote and not loc else loc,
                    url=str(j.get("url") or ""),
                    description=str(j.get("description") or ""),
                    source="arbeitnow",
                    job_id=str(j.get("slug") or ""),
                    remote=remote,
                    workplace="remote" if remote else "",
                )
            )
        emit(on_event, "arbeitnow", f"page {page}: +{len(jobs)} raw → {len(out)} kept so far")
    return out


def fetch_himalayas(cfg: dict[str, Any], on_event: EventCallback | None = None) -> list[dict[str, Any]]:
    keywords = list(cfg.get("search_keywords") or [])[:12]
    limit = int(cfg.get("himalayas_limit") or 80)
    headers = {"User-Agent": UA, "Accept": "application/json"}
    out: list[dict[str, Any]] = []
    emit(on_event, "himalayas", "Himalayas remote jobs API")
    # Public search endpoint variants
    urls = [
        ("https://himalayas.app/jobs/api", {"limit": min(limit, 100)}),
        ("https://himalayas.app/jobs/api/search", {"limit": min(limit, 50), "q": "data"}),
    ]
    for api, params in urls:
        try:
            resp = requests.get(api, params=params, headers=headers, timeout=30)
            if resp.status_code >= 400:
                continue
            data = resp.json()
            jobs = data if isinstance(data, list) else (data.get("jobs") or data.get("data") or [])
        except Exception as exc:  # noqa: BLE001
            emit(on_event, "warning", f"Himalayas failed ({api}): {exc}")
            continue
        for j in jobs:
            title = str(j.get("title") or j.get("jobTitle") or "")
            if keywords and not _title_matches(title, keywords):
                blob = f"{title} {' '.join(str(x) for x in (j.get('categories') or j.get('skills') or []))}"
                if not re.search(r"\b(data|ai|ml|analytics|engineer|scientist|cloud|aws)\b", blob.lower()):
                    continue
            url = str(j.get("applicationLink") or j.get("url") or j.get("guid") or "")
            out.append(
                _norm_item(
                    title=title,
                    company=str(j.get("companyName") or j.get("company") or ""),
                    location=str(j.get("location") or "Remote"),
                    url=url or f"https://himalayas.app/jobs/{j.get('id') or ''}",
                    description=str(j.get("description") or ""),
                    source="himalayas",
                    job_id=str(j.get("id") or ""),
                    remote=True,
                    workplace="remote",
                )
            )
        if out:
            break
    emit(on_event, "himalayas", f"kept {len(out)} jobs")
    return out


def fetch_remotive(cfg: dict[str, Any], on_event: EventCallback | None = None) -> list[dict[str, Any]]:
    headers = {"User-Agent": UA, "Accept": "application/json"}
    categories = cfg.get("remotive_categories") or ["data", "software-dev"]
    keywords = list(cfg.get("search_keywords") or [])
    out: list[dict[str, Any]] = []
    emit(on_event, "remotive", f"Remotive categories: {categories}")
    for cat in categories:
        try:
            resp = requests.get(
                "https://remotive.com/api/remote-jobs",
                params={"category": cat},
                headers=headers,
                timeout=30,
            )
            resp.raise_for_status()
            jobs = (resp.json() or {}).get("jobs") or []
        except Exception as exc:  # noqa: BLE001
            emit(on_event, "warning", f"Remotive/{cat} failed: {exc}")
            continue
        for j in jobs:
            title = str(j.get("title") or "")
            if keywords and not _title_matches(title, keywords):
                if not re.search(r"\b(data|ai|ml|analytics|scientist|engineer|aws|cloud|etl|bi)\b", title.lower()):
                    continue
            out.append(
                _norm_item(
                    title=title,
                    company=str(j.get("company_name") or ""),
                    location=str(j.get("candidate_required_location") or "Remote"),
                    url=str(j.get("url") or ""),
                    description=str(j.get("description") or ""),
                    source="remotive",
                    job_id=str(j.get("id") or ""),
                    remote=True,
                    workplace="remote",
                )
            )
    emit(on_event, "remotive", f"kept {len(out)} jobs")
    return out


def fetch_ba_api(cfg: dict[str, Any], on_event: EventCallback | None = None) -> list[dict[str, Any]]:
    queries = list(cfg.get("ba_queries") or [])[: int(cfg.get("ba_queries_per_run") or 6)]
    if not queries:
        return []
    headers = {
        "X-API-Key": "jobboerse-jobsuche",
        "Accept": "application/json",
        "User-Agent": UA,
    }
    url = "https://rest.arbeitsagentur.de/jobboerse/jobsuche-service/pc/v6/jobs"
    out: list[dict[str, Any]] = []
    size = int(cfg.get("ba_page_size") or 25)
    emit(on_event, "ba_api", f"BA Jobsuche - {len(queries)} queries")
    for q in queries:
        try:
            resp = requests.get(url, headers=headers, params={"was": q, "size": size, "page": 1}, timeout=30)
            resp.raise_for_status()
            payload = resp.json() or {}
            jobs = payload.get("ergebnisliste") or payload.get("stellenangebote") or []
        except Exception as exc:  # noqa: BLE001
            emit(on_event, "warning", f"BA query failed ({q}): {exc}")
            continue
        for j in jobs:
            title = str(
                j.get("stellenangebotsTitel")
                or j.get("titel")
                or j.get("beruf")
                or j.get("hauptberuf")
                or ""
            )
            company = str(j.get("firma") or "")
            if not company:
                ag = j.get("arbeitsgeber") or j.get("arbeitgeber") or {}
                if isinstance(ag, dict):
                    company = str(ag.get("name") or "")
                else:
                    company = str(ag or "")
            loc = ""
            locs = j.get("stellenlokationen") or []
            if locs and isinstance(locs[0], dict):
                addr = locs[0].get("adresse") or {}
                loc = str(addr.get("ort") or addr.get("region") or addr.get("land") or "")
            if not loc:
                ao = j.get("arbeitsort")
                if isinstance(ao, dict):
                    loc = str(ao.get("ort") or ao.get("region") or "Germany")
                else:
                    loc = str(ao or "Germany")
            ref = str(j.get("referenznummer") or j.get("refnr") or j.get("hashId") or "")
            apply = str(j.get("externeURL") or "")
            if not apply and ref:
                apply = f"https://www.arbeitsagentur.de/jobsuche/jobdetail/{ref}"
            remote = bool(j.get("homeofficemoeglich"))
            out.append(
                _norm_item(
                    title=title,
                    company=company,
                    location="Remote" if remote and not loc else loc,
                    url=apply,
                    description=str(j.get("stellenbeschreibung") or ""),
                    source="ba_api",
                    job_id=ref,
                    remote=remote,
                    workplace="remote" if remote else "",
                )
            )
        emit(on_event, "ba_api", f"query '{q}': {len(jobs)} hits (total kept {len(out)})")
    return out


def _load_ats_boards(cfg: dict[str, Any]) -> dict[str, list[str]]:
    path = ROOT / str(cfg.get("ats_boards_file") or "config/ats_boards.yaml")
    keys = (
        "greenhouse",
        "ashby",
        "lever",
        "smartrecruiters",
        "workable",
        "recruitee",
        "pinpoint",
        "teamtailor",
        "comeet",
    )
    if path.is_file():
        with path.open(encoding="utf-8") as fh:
            data = yaml.safe_load(fh) or {}
        return {k: list(data.get(k) or []) for k in keys}
    ats = cfg.get("ats") or {}
    return {k: list(ats.get(k) or []) for k in keys}


def _pick_rotated(items: list[str], n: int, salt: int) -> list[str]:
    if not items or n <= 0:
        return []
    if n >= len(items):
        return list(items)
    start = salt % len(items)
    return [items[(start + i) % len(items)] for i in range(n)]


def _ats_title_keys(cfg: dict[str, Any]) -> list[str]:
    keys = list(cfg.get("search_keywords") or []) + list(cfg.get("job_roles") or [])
    # Prefer compact tokens that match titles like "Senior ML Engineer"
    compact = [
        "data scientist",
        "data analyst",
        "data engineer",
        "analytics engineer",
        "machine learning",
        "ml engineer",
        "mlops",
        "ai engineer",
        "deep learning",
        "business intelligence",
        "bi analyst",
        "bi developer",
        "business analyst",
        "quantitative",
        "data architect",
        "cloud architect",
        "cloud data",
        "dataops",
        "data consultant",
        "data governance",
        "data visualization",
        "market research",
        "database",
        "big data",
        "sagemaker",
        "snowflake",
        "databricks",
        "dbt",
        "spark",
        "aws",
        "azure",
        "gcp",
        "genai",
        "generative ai",
        "llm",
        "nlp",
        "computer vision",
        "product manager data",
        "solutions architect",
        "werkstudent",
        "working student",
        "daten",
        "ki ",
    ]
    out = []
    seen = set()
    for k in compact + [x.lower() for x in keys]:
        k = k.strip().lower()
        if len(k) >= 3 and k not in seen:
            seen.add(k)
            out.append(k)
    return out[:120]


def fetch_smartrecruiters(
    companies: list[str], keywords: list[str], on_event: EventCallback | None = None
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    headers = {"User-Agent": UA, "Accept": "application/json"}
    for company in companies:
        try:
            resp = requests.get(
                f"https://api.smartrecruiters.com/v1/companies/{company}/postings",
                params={"limit": 100},
                headers=headers,
                timeout=30,
            )
            if resp.status_code >= 400:
                emit(on_event, "warning", f"SmartRecruiters/{company} -> HTTP {resp.status_code}")
                continue
            jobs = (resp.json() or {}).get("content") or []
        except Exception as exc:  # noqa: BLE001
            emit(on_event, "warning", f"SmartRecruiters/{company} failed: {exc}")
            continue
        kept = 0
        for j in jobs:
            title = str(j.get("name") or "")
            if keywords and not _title_matches(title, keywords):
                continue
            loc = ""
            loc_obj = j.get("location") or {}
            if isinstance(loc_obj, dict):
                loc = ", ".join(
                    x for x in [loc_obj.get("city"), loc_obj.get("region"), loc_obj.get("country")] if x
                )
            pid = str(j.get("id") or "")
            url = str(j.get("ref") or "")
            if not url and pid:
                url = f"https://jobs.smartrecruiters.com/{company}/{pid}"
            out.append(
                _norm_item(
                    title=title,
                    company=company,
                    location=loc,
                    url=url,
                    description="",
                    source="smartrecruiters",
                    job_id=pid,
                )
            )
            kept += 1
        emit(on_event, "smartrecruiters", f"{company}: {kept} matching of {len(jobs)}")
    return out


def fetch_workable(
    accounts: list[str], keywords: list[str], on_event: EventCallback | None = None
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    headers = {"User-Agent": UA, "Accept": "application/json"}
    for account in accounts:
        try:
            resp = requests.get(
                f"https://apply.workable.com/api/v1/widget/accounts/{account}",
                headers=headers,
                timeout=30,
            )
            if resp.status_code >= 400:
                emit(on_event, "warning", f"Workable/{account} -> HTTP {resp.status_code}")
                continue
            jobs = (resp.json() or {}).get("jobs") or []
        except Exception as exc:  # noqa: BLE001
            emit(on_event, "warning", f"Workable/{account} failed: {exc}")
            continue
        kept = 0
        for j in jobs:
            title = str(j.get("title") or "")
            if keywords and not _title_matches(title, keywords):
                continue
            loc = str(j.get("location") or j.get("city") or "")
            url = str(j.get("url") or "")
            if url and url.startswith("/"):
                url = f"https://apply.workable.com{url}"
            out.append(
                _norm_item(
                    title=title,
                    company=account,
                    location=loc,
                    url=url,
                    description="",
                    source="workable",
                    job_id=str(j.get("shortcode") or j.get("id") or ""),
                    remote=bool(j.get("remote")),
                    workplace="remote" if j.get("remote") else "",
                )
            )
            kept += 1
        emit(on_event, "workable", f"{account}: {kept} matching of {len(jobs)}")
    return out


def fetch_recruitee(
    companies: list[str], keywords: list[str], on_event: EventCallback | None = None
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    headers = {"User-Agent": UA, "Accept": "application/json"}
    for company in companies:
        try:
            resp = requests.get(
                f"https://{company}.recruitee.com/api/offers",
                headers=headers,
                timeout=30,
            )
            if resp.status_code >= 400:
                emit(on_event, "warning", f"Recruitee/{company} -> HTTP {resp.status_code}")
                continue
            jobs = (resp.json() or {}).get("offers") or []
        except Exception as exc:  # noqa: BLE001
            emit(on_event, "warning", f"Recruitee/{company} failed: {exc}")
            continue
        kept = 0
        for j in jobs:
            title = str(j.get("title") or "")
            if keywords and not _title_matches(title, keywords):
                continue
            loc = str(j.get("location") or "")
            url = str(j.get("careers_url") or j.get("url") or "")
            out.append(
                _norm_item(
                    title=title,
                    company=company,
                    location=loc,
                    url=url,
                    description=str(j.get("description") or ""),
                    source="recruitee",
                    job_id=str(j.get("id") or ""),
                    remote=bool(j.get("remote")),
                    workplace="remote" if j.get("remote") else "",
                )
            )
            kept += 1
        emit(on_event, "recruitee", f"{company}: {kept} matching of {len(jobs)}")
    return out


def fetch_ats_all(cfg: dict[str, Any], on_event: EventCallback | None = None) -> list[dict[str, Any]]:
    from datetime import date

    from .ats_extended import (
        fetch_comeet,
        fetch_personio_tenants,
        fetch_pinpoint,
        fetch_teamtailor,
        fetch_workday,
        load_personio_tenants,
        load_workday_targets,
    )

    boards = _load_ats_boards(cfg)
    salt = date.today().toordinal()
    n_gh = int(cfg.get("ats_greenhouse_per_run") or 25)
    n_ash = int(cfg.get("ats_ashby_per_run") or 12)
    n_lev = int(cfg.get("ats_lever_per_run") or 6)
    n_sr = int(cfg.get("ats_smartrecruiters_per_run") or 12)
    n_wk = int(cfg.get("ats_workable_per_run") or 3)
    n_rc = int(cfg.get("ats_recruitee_per_run") or 2)
    n_pp = int(cfg.get("ats_pinpoint_per_run") or 4)
    n_tt = int(cfg.get("ats_teamtailor_per_run") or 4)
    n_cm = int(cfg.get("ats_comeet_per_run") or 3)
    n_pe = int(cfg.get("ats_personio_per_run") or 8)
    n_wd = int(cfg.get("ats_workday_per_run") or 3)
    title_keys = _ats_title_keys(cfg)

    gh = _pick_rotated(boards["greenhouse"], n_gh, salt)
    ash = _pick_rotated(boards["ashby"], n_ash, salt + 3)
    lev = _pick_rotated(boards["lever"], n_lev, salt + 7)
    sr = _pick_rotated(boards["smartrecruiters"], n_sr, salt + 11)
    wk = _pick_rotated(boards["workable"], n_wk, salt + 13)
    rc = _pick_rotated(boards["recruitee"], n_rc, salt + 17)
    pp = _pick_rotated(boards["pinpoint"], n_pp, salt + 19)
    tt = _pick_rotated(boards["teamtailor"], n_tt, salt + 23)
    cm = _pick_rotated(boards["comeet"], n_cm, salt + 29)
    personio_all = load_personio_tenants(cfg)
    if personio_all:
        if n_pe >= len(personio_all):
            personio = list(personio_all)
        else:
            start = (salt + 31) % len(personio_all)
            personio = [personio_all[(start + i) % len(personio_all)] for i in range(n_pe)]
    else:
        personio = []
    workday_all = load_workday_targets(cfg)
    if workday_all:
        if n_wd >= len(workday_all):
            workday = list(workday_all)
        else:
            start = (salt + 37) % len(workday_all)
            workday = [workday_all[(start + i) % len(workday_all)] for i in range(n_wd)]
    else:
        workday = []

    emit(
        on_event,
        "ats",
        "ATS this run: "
        f"GH={len(gh)} Ashby={len(ash)} Lever={len(lev)} SR={len(sr)} "
        f"Workable={len(wk)} Recruitee={len(rc)} Pinpoint={len(pp)} "
        f"Teamtailor={len(tt)} Comeet={len(cm)} Personio={len(personio)} Workday={len(workday)}",
    )

    items: list[dict[str, Any]] = []
    items.extend(fetch_greenhouse(gh, title_keys, on_event))
    items.extend(fetch_ashby(ash, title_keys, on_event))
    items.extend(fetch_lever(lev, title_keys, on_event))
    items.extend(fetch_smartrecruiters(sr, title_keys, on_event))
    items.extend(fetch_workable(wk, title_keys, on_event))
    items.extend(fetch_recruitee(rc, title_keys, on_event))
    items.extend(fetch_pinpoint(pp, title_keys, on_event))
    items.extend(fetch_teamtailor(tt, title_keys, on_event))
    items.extend(fetch_comeet(cm, title_keys, on_event))
    items.extend(fetch_personio_tenants(personio, title_keys, on_event))
    items.extend(fetch_workday(workday, title_keys, on_event))
    return items


def fetch_greenhouse(boards: list[str], keywords: list[str], on_event: EventCallback | None = None) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    headers = {"User-Agent": UA, "Accept": "application/json"}
    for board in boards:
        try:
            resp = requests.get(
                f"https://boards-api.greenhouse.io/v1/boards/{board}/jobs",
                params={"content": "true"},
                headers=headers,
                timeout=30,
            )
            if resp.status_code >= 400:
                emit(on_event, "warning", f"Greenhouse/{board} -> HTTP {resp.status_code}")
                continue
            jobs = (resp.json() or {}).get("jobs") or []
        except Exception as exc:  # noqa: BLE001
            emit(on_event, "warning", f"Greenhouse/{board} failed: {exc}")
            continue
        kept = 0
        for j in jobs:
            title = str(j.get("title") or "")
            if keywords and not _title_matches(title, keywords):
                continue
            loc_parts = []
            for loc in j.get("offices") or []:
                if isinstance(loc, dict) and loc.get("name"):
                    loc_parts.append(str(loc["name"]))
            loc_obj = j.get("location")
            if isinstance(loc_obj, dict) and loc_obj.get("name"):
                loc_parts.append(str(loc_obj["name"]))
            location = ", ".join(dict.fromkeys(loc_parts))
            abs_url = str(j.get("absolute_url") or "")
            out.append(
                _norm_item(
                    title=title,
                    company=board,
                    location=location,
                    url=abs_url,
                    description=str(j.get("content") or ""),
                    source="greenhouse",
                    job_id=str(j.get("id") or ""),
                )
            )
            kept += 1
        emit(on_event, "greenhouse", f"{board}: {kept} matching of {len(jobs)}")
    return out


def fetch_ashby(boards: list[str], keywords: list[str], on_event: EventCallback | None = None) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    headers = {"User-Agent": UA, "Accept": "application/json"}
    for board in boards:
        try:
            resp = requests.get(
                f"https://api.ashbyhq.com/posting-api/job-board/{board}",
                headers=headers,
                timeout=30,
            )
            if resp.status_code >= 400:
                emit(on_event, "warning", f"Ashby/{board} → HTTP {resp.status_code}")
                continue
            jobs = (resp.json() or {}).get("jobs") or []
        except Exception as exc:  # noqa: BLE001
            emit(on_event, "warning", f"Ashby/{board} failed: {exc}")
            continue
        kept = 0
        for j in jobs:
            title = str(j.get("title") or "")
            if keywords and not _title_matches(title, keywords):
                continue
            loc = str(j.get("location") or "")
            url = str(j.get("jobUrl") or j.get("applyUrl") or "")
            out.append(
                _norm_item(
                    title=title,
                    company=str(j.get("department") or board),
                    location=loc,
                    url=url,
                    description=str(j.get("descriptionPlain") or j.get("descriptionHtml") or ""),
                    source="ashby",
                    job_id=str(j.get("id") or ""),
                    workplace="remote" if j.get("isRemote") else "",
                    remote=bool(j.get("isRemote")),
                )
            )
            kept += 1
        emit(on_event, "ashby", f"{board}: {kept} matching of {len(jobs)}")
    return out


def fetch_lever(companies: list[str], keywords: list[str], on_event: EventCallback | None = None) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    headers = {"User-Agent": UA, "Accept": "application/json"}
    for company in companies:
        try:
            resp = requests.get(
                f"https://api.lever.co/v0/postings/{company}",
                params={"mode": "json"},
                headers=headers,
                timeout=30,
            )
            if resp.status_code >= 400:
                emit(on_event, "warning", f"Lever/{company} → HTTP {resp.status_code}")
                continue
            payload = resp.json()
            jobs = payload if isinstance(payload, list) else []
        except Exception as exc:  # noqa: BLE001
            emit(on_event, "warning", f"Lever/{company} failed: {exc}")
            continue
        kept = 0
        for j in jobs:
            title = str(j.get("text") or "")
            if keywords and not _title_matches(title, keywords):
                continue
            cats = j.get("categories") or {}
            loc = str(cats.get("location") or "")
            url = str(j.get("hostedUrl") or j.get("applyUrl") or "")
            out.append(
                _norm_item(
                    title=title,
                    company=company,
                    location=loc,
                    url=url,
                    description=str((j.get("descriptionPlain") or j.get("description") or "")),
                    source="lever",
                    job_id=str(j.get("id") or ""),
                    workplace=str(cats.get("commitment") or ""),
                )
            )
            kept += 1
        emit(on_event, "lever", f"{company}: {kept} matching of {len(jobs)}")
    return out


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
