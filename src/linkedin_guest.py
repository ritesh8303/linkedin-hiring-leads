"""LinkedIn public guest jobs endpoints (no login, no Apify)."""

from __future__ import annotations

import re
import time
from typing import Any

import requests
from bs4 import BeautifulSoup

SEARCH_URL = "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"
DETAIL_URL = "https://www.linkedin.com/jobs-guest/jobs/api/jobPosting/{job_id}"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}

# LinkedIn time windows
_TPR = {
    "past24h": "r86400",
    "pastWeek": "r604800",
    "pastMonth": "r2592000",
    "all": "",
}


def _session() -> requests.Session:
    s = requests.Session()
    s.headers.update(HEADERS)
    return s


def _parse_job_id(card: Any) -> str:
    urn = ""
    base = card.select_one("div.base-card") or card.select_one("div.job-search-card") or card
    if base and base.has_attr("data-entity-urn"):
        urn = base["data-entity-urn"]
    if not urn:
        link = card.select_one("a.base-card__full-link") or card.select_one("a[href*='/jobs/view/']")
        if link and link.has_attr("href"):
            m = re.search(r"/jobs/view/[^/]*?(\d+)", link["href"])
            if m:
                return m.group(1)
    m = re.search(r"(\d+)$", urn or "")
    return m.group(1) if m else ""


def _text(el: Any) -> str:
    return el.get_text(" ", strip=True) if el else ""


def fetch_search_page(
    session: requests.Session,
    *,
    keywords: str,
    location: str,
    start: int = 0,
    date_posted: str = "pastMonth",
    entry_level_only: bool = False,
    workplace_types: list[str] | None = None,
) -> list[dict[str, Any]]:
    params_list: list[tuple[str, str]] = [
        ("keywords", keywords),
        ("location", location),
        ("start", str(start)),
        ("sortBy", "DD"),
    ]
    tpr = _TPR.get(date_posted, "r2592000")
    if tpr:
        params_list.append(("f_TPR", tpr))
    if entry_level_only:
        params_list.append(("f_E", "1"))
        params_list.append(("f_E", "2"))
    # LinkedIn: 1=On-site, 2=Remote, 3=Hybrid
    wt_map = {"on-site": "1", "onsite": "1", "remote": "2", "hybrid": "3"}
    for wt in workplace_types or []:
        code = wt_map.get(str(wt).strip().lower())
        if code:
            params_list.append(("f_WT", code))

    resp = session.get(SEARCH_URL, params=params_list, timeout=30)
    if resp.status_code == 429:
        raise RuntimeError("LinkedIn guest rate-limited (429). Wait a bit and retry.")
    resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "html.parser")
    cards = soup.select("li")
    jobs: list[dict[str, Any]] = []
    for card in cards:
        job_id = _parse_job_id(card)
        if not job_id:
            continue
        title = _text(card.select_one("h3.base-search-card__title") or card.select_one("h3"))
        company = _text(card.select_one("h4.base-search-card__subtitle") or card.select_one("a.hidden-nested-link"))
        loc = _text(card.select_one("span.job-search-card__location"))
        link_el = card.select_one("a.base-card__full-link") or card.select_one("a[href*='/jobs/view/']")
        href = link_el["href"].split("?")[0] if link_el and link_el.has_attr("href") else ""
        if href and href.startswith("/"):
            href = "https://www.linkedin.com" + href
        posted = _text(card.select_one("time"))
        time_el = card.select_one("time")
        posted_iso = time_el.get("datetime", "") if time_el else ""
        jobs.append(
            {
                "jobId": job_id,
                "title": title,
                "company": company,
                "companyName": company,
                "location": loc,
                "jobUrl": href or f"https://www.linkedin.com/jobs/view/{job_id}",
                "postedDate": posted_iso or posted,
                "description": "",
                "seniorityLevel": "",
                "employmentType": "",
                "source": "linkedin_guest",
                "searchKeywords": keywords,
                "searchLocation": location,
            }
        )
    return jobs


def enrich_job_detail(session: requests.Session, job: dict[str, Any]) -> dict[str, Any]:
    job_id = job.get("jobId") or ""
    if not job_id:
        return job
    url = DETAIL_URL.format(job_id=job_id)
    resp = session.get(url, timeout=30)
    if resp.status_code == 429:
        raise RuntimeError("LinkedIn guest rate-limited on detail fetch (429).")
    if resp.status_code != 200:
        return job
    soup = BeautifulSoup(resp.text, "html.parser")
    desc = soup.select_one("div.show-more-less-html__markup") or soup.select_one("div.description__text")
    if desc:
        job["description"] = desc.get_text("\n", strip=True)

    criteria_map: dict[str, str] = {}
    for item in soup.select("li.description__job-criteria-item"):
        header = _text(item.select_one("h3")).lower()
        value = _text(item.select_one("span.description__job-criteria-text"))
        if header and value:
            criteria_map[header] = value
    job["seniorityLevel"] = criteria_map.get("seniority level", job.get("seniorityLevel") or "")
    job["employmentType"] = criteria_map.get("employment type", job.get("employmentType") or "")
    if not job.get("title"):
        job["title"] = _text(soup.select_one("h1"))
    if not job.get("company"):
        company = _text(soup.select_one("a.topcard__org-name-link") or soup.select_one("span.topcard__flavor"))
        job["company"] = company
        job["companyName"] = company
    if not job.get("location"):
        job["location"] = _text(soup.select_one("span.topcard__flavor--bullet"))
    return job


def fetch_linkedin_guest_jobs(
    *,
    keywords: str,
    location: str,
    max_results: int = 40,
    date_posted: str = "pastMonth",
    entry_level_only: bool = False,
    fetch_details: bool = True,
    delay_sec: float = 1.5,
    workplace_types: list[str] | None = None,
) -> list[dict[str, Any]]:
    session = _session()
    collected: list[dict[str, Any]] = []
    seen: set[str] = set()
    start = 0

    while len(collected) < max_results:
        page = fetch_search_page(
            session,
            keywords=keywords,
            location=location,
            start=start,
            date_posted=date_posted,
            entry_level_only=entry_level_only,
            workplace_types=workplace_types,
        )
        if not page:
            break
        for job in page:
            jid = job["jobId"]
            if jid in seen:
                continue
            seen.add(jid)
            collected.append(job)
            if len(collected) >= max_results:
                break
        if len(page) < 10:
            break
        start += 25
        time.sleep(delay_sec)

    if fetch_details:
        detailed: list[dict[str, Any]] = []
        for job in collected:
            try:
                detailed.append(enrich_job_detail(session, job))
            except Exception:
                detailed.append(job)
            time.sleep(delay_sec)
        return detailed
    return collected
