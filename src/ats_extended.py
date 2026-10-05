"""Extended public ATS fetchers: Personio, Pinpoint, Teamtailor, Comeet, Workday."""

from __future__ import annotations

import time
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

import requests
import yaml

from .free_sources import _norm_item, _title_matches
from .progress import EventCallback, emit

ROOT = Path(__file__).resolve().parents[1]
UA = "PersonalJobRadar/1.0 (+https://github.com/ritesh8303/linkedin-hiring-leads; local research)"


def _headers() -> dict[str, str]:
    return {"User-Agent": UA, "Accept": "application/json, application/xml, text/xml, */*"}


def fetch_personio_tenants(
    tenants: list[dict[str, Any]],
    keywords: list[str],
    on_event: EventCallback | None = None,
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for entry in tenants:
        slug = str(entry.get("slug") or "").strip()
        if not slug:
            continue
        tld = str(entry.get("tld") or "de").strip().lstrip(".")
        company = str(entry.get("company") or slug)
        hosts = [
            f"https://{slug}.jobs.personio.{tld}/xml",
            f"https://{slug}.jobs.personio.{'com' if tld == 'de' else 'de'}/xml",
        ]
        text = ""
        used = hosts[0]
        for host in hosts:
            try:
                resp = requests.get(
                    host,
                    params={"language": "en"},
                    headers=_headers(),
                    timeout=25,
                    allow_redirects=False,
                )
                if resp.status_code in {301, 302, 303, 307, 308}:
                    continue
                if resp.status_code == 429:
                    time.sleep(1.5)
                    continue
                if resp.status_code >= 400:
                    continue
                text = resp.text
                used = host
                break
            except Exception as exc:  # noqa: BLE001
                emit(on_event, "warning", f"Personio/{slug} failed: {exc}")
                continue
        if not text:
            emit(on_event, "warning", f"Personio/{slug} -> no XML feed")
            continue
        try:
            root = ET.fromstring(text)
        except ET.ParseError as exc:
            emit(on_event, "warning", f"Personio/{slug} XML parse error: {exc}")
            continue
        base = used.rsplit("/xml", 1)[0]
        kept = 0
        total = 0
        for job in list(root):
            total += 1
            fields = {
                child.tag.split("}", 1)[-1].lower(): "".join(child.itertext()).strip()
                for child in list(job)
            }
            title = fields.get("name") or fields.get("title") or fields.get("jobtitle") or ""
            if keywords and not _title_matches(title, keywords):
                continue
            raw_id = fields.get("id") or fields.get("jobid") or ""
            loc = fields.get("office") or fields.get("location") or ""
            desc = "\n".join(
                x
                for x in [
                    fields.get("jobdescription"),
                    fields.get("description"),
                    fields.get("profile"),
                ]
                if x
            )
            out.append(
                _norm_item(
                    title=title,
                    company=company,
                    location=loc,
                    url=fields.get("url") or (f"{base}/job/{raw_id}" if raw_id else base),
                    description=desc,
                    source="personio",
                    job_id=str(raw_id),
                    workplace=fields.get("workplace") or "",
                    remote=(fields.get("workplace") or "").lower() == "remote",
                )
            )
            kept += 1
        emit(on_event, "personio", f"{slug}: {kept} matching of {total}")
        time.sleep(0.2)
    return out


def fetch_pinpoint(
    boards: list[str], keywords: list[str], on_event: EventCallback | None = None
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for slug in boards:
        try:
            resp = requests.get(
                f"https://{slug}.pinpointhq.com/postings.json",
                headers=_headers(),
                timeout=30,
            )
            if resp.status_code >= 400:
                emit(on_event, "warning", f"Pinpoint/{slug} -> HTTP {resp.status_code}")
                continue
            data = resp.json() or {}
            jobs = data.get("data") if isinstance(data, dict) else data
            jobs = jobs or []
        except Exception as exc:  # noqa: BLE001
            emit(on_event, "warning", f"Pinpoint/{slug} failed: {exc}")
            continue
        kept = 0
        for j in jobs:
            title = str(j.get("title") or "")
            if keywords and not _title_matches(title, keywords):
                continue
            loc = j.get("location")
            if isinstance(loc, dict):
                loc = loc.get("name") or ""
            url = str(j.get("url") or "")
            if not url and j.get("path"):
                url = f"https://{slug}.pinpointhq.com{j.get('path')}"
            out.append(
                _norm_item(
                    title=title,
                    company=slug,
                    location=str(loc or ""),
                    url=url,
                    description=str(j.get("description") or ""),
                    source="pinpoint",
                    job_id=str(j.get("id") or ""),
                    workplace=str(j.get("workplace_type_text") or j.get("workplace_type") or ""),
                )
            )
            kept += 1
        emit(on_event, "pinpoint", f"{slug}: {kept} matching of {len(jobs)}")
    return out


def fetch_teamtailor(
    hosts: list[str], keywords: list[str], on_event: EventCallback | None = None
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for host in hosts:
        host = host.replace("https://", "").replace("http://", "").strip("/")
        url = f"https://{host}/jobs.rss?per_page=200"
        try:
            resp = requests.get(url, headers=_headers(), timeout=30)
            if resp.status_code >= 400:
                emit(on_event, "warning", f"Teamtailor/{host} -> HTTP {resp.status_code}")
                continue
            root = ET.fromstring(resp.content)
        except Exception as exc:  # noqa: BLE001
            emit(on_event, "warning", f"Teamtailor/{host} failed: {exc}")
            continue
        items = root.findall(".//item")
        kept = 0
        for item in items:
            title = (item.findtext("title") or "").strip()
            if keywords and not _title_matches(title, keywords):
                continue
            link = (item.findtext("link") or "").strip()
            desc = (item.findtext("description") or "").strip()
            out.append(
                _norm_item(
                    title=title,
                    company=host.split(".")[0],
                    location="",
                    url=link,
                    description=desc,
                    source="teamtailor",
                    job_id=link.rsplit("/", 1)[-1] if link else "",
                )
            )
            kept += 1
        emit(on_event, "teamtailor", f"{host}: {kept} matching of {len(items)}")
    return out


def fetch_comeet(
    company_uids: list[str], keywords: list[str], on_event: EventCallback | None = None
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for uid in company_uids:
        try:
            resp = requests.get(
                f"https://www.comeet.co/careers-api/2.0/company/{uid}/positions",
                params={"details": "true"},
                headers=_headers(),
                timeout=30,
            )
            if resp.status_code >= 400:
                emit(on_event, "warning", f"Comeet/{uid} -> HTTP {resp.status_code}")
                continue
            data = resp.json() or {}
            jobs = data.get("positions") if isinstance(data, dict) else data
            jobs = jobs or []
        except Exception as exc:  # noqa: BLE001
            emit(on_event, "warning", f"Comeet/{uid} failed: {exc}")
            continue
        kept = 0
        for j in jobs:
            title = str(j.get("name") or j.get("title") or "")
            if keywords and not _title_matches(title, keywords):
                continue
            loc = j.get("location") or {}
            location = loc.get("name") if isinstance(loc, dict) else str(loc or "")
            out.append(
                _norm_item(
                    title=title,
                    company=uid,
                    location=str(location or ""),
                    url=str(j.get("url") or j.get("absolute_url") or ""),
                    description=str(j.get("description") or j.get("details") or ""),
                    source="comeet",
                    job_id=str(j.get("uid") or j.get("id") or ""),
                )
            )
            kept += 1
        emit(on_event, "comeet", f"{uid}: {kept} matching of {len(jobs)}")
    return out


def fetch_workday(
    targets: list[dict[str, Any]],
    keywords: list[str],
    on_event: EventCallback | None = None,
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for entry in targets:
        host = str(entry.get("host") or "").rstrip("/")
        tenant = str(entry.get("tenant") or "")
        site = str(entry.get("site") or "")
        company = str(entry.get("company") or tenant)
        if not (host and tenant and site):
            continue
        api = f"{host}/wday/cxs/{tenant}/{site}/jobs"
        try:
            resp = requests.post(
                api,
                headers={**_headers(), "Content-Type": "application/json"},
                json={"appliedFacets": {}, "limit": 50, "offset": 0, "searchText": ""},
                timeout=40,
            )
            if resp.status_code >= 400:
                emit(on_event, "warning", f"Workday/{company} -> HTTP {resp.status_code}")
                continue
            jobs = (resp.json() or {}).get("jobPostings") or []
        except Exception as exc:  # noqa: BLE001
            emit(on_event, "warning", f"Workday/{company} failed: {exc}")
            continue
        kept = 0
        for j in jobs:
            title = str(j.get("title") or "")
            if keywords and not _title_matches(title, keywords):
                continue
            path = str(j.get("externalPath") or "")
            url = f"{host}/{site}{path}" if path else host
            out.append(
                _norm_item(
                    title=title,
                    company=company,
                    location=str(j.get("locationsText") or ""),
                    url=url,
                    description="",
                    source="workday",
                    job_id=path or title,
                    workplace=str(j.get("remoteType") or ""),
                )
            )
            kept += 1
        emit(on_event, "workday", f"{company}: {kept} matching of {len(jobs)}")
    return out


def load_personio_tenants(cfg: dict[str, Any]) -> list[dict[str, Any]]:
    path = ROOT / str(cfg.get("personio_tenants_file") or "config/personio_tenants.json")
    if not path.is_file():
        return []
    import json

    data = json.loads(path.read_text(encoding="utf-8"))
    return data if isinstance(data, list) else []


def load_workday_targets(cfg: dict[str, Any]) -> list[dict[str, Any]]:
    path = ROOT / str(cfg.get("workday_targets_file") or "config/workday_targets.yaml")
    if not path.is_file():
        return []
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or []
    return data if isinstance(data, list) else []
