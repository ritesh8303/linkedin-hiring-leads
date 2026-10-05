"""Google Jobs via SerpAPI free tier."""

from __future__ import annotations

from typing import Any

import requests


SERPAPI_URL = "https://serpapi.com/search.json"


def fetch_google_jobs(
    *,
    api_key: str,
    keywords: str,
    location: str = "Germany",
    max_results: int = 40,
    chips: str | None = None,
) -> list[dict[str, Any]]:
    if not api_key:
        raise ValueError(
            "Missing SERPAPI_API_KEY. Get a free key at https://serpapi.com/manage-api-key"
        )

    # City-level locations can be flaky; prefer gl=de and put country in the query.
    attempts = [
        {"q": keywords, "google_domain": "google.de", "gl": "de", "hl": "de"},
        {"q": f"{keywords} Deutschland", "google_domain": "google.de", "gl": "de", "hl": "de"},
        {"q": keywords, "location": "Berlin", "google_domain": "google.de", "gl": "de", "hl": "de"},
        {"q": f"{keywords} Germany", "gl": "de", "hl": "en"},
        {"q": keywords, "gl": "de", "hl": "en"},
    ]

    last_error = ""
    for attempt in attempts:
        params: dict[str, Any] = {
            "engine": "google_jobs",
            "api_key": api_key,
            **attempt,
        }
        if chips:
            params["chips"] = chips

        jobs: list[dict[str, Any]] = []
        next_token: str | None = None

        while len(jobs) < max_results:
            call = dict(params)
            if next_token:
                call["next_page_token"] = next_token
            resp = requests.get(SERPAPI_URL, params=call, timeout=60)
            resp.raise_for_status()
            data = resp.json()
            if data.get("error"):
                last_error = str(data["error"])
                break

            batch = data.get("jobs_results") or []
            if not batch:
                break

            for item in batch:
                jobs.append(_normalize(item, keywords, location))
                if len(jobs) >= max_results:
                    break

            next_token = (data.get("serpapi_pagination") or {}).get("next_page_token")
            if not next_token:
                break

        if jobs:
            return jobs[:max_results]

    if last_error:
        raise RuntimeError(f"SerpAPI error: {last_error}")
    return []


def _normalize(item: dict[str, Any], keywords: str, location: str) -> dict[str, Any]:
    ext = item.get("detected_extensions") or {}
    links = item.get("related_links") or []
    apply_link = ""
    for link in links:
        href = link.get("link") or ""
        if href:
            apply_link = href
            break
    job_id = str(item.get("job_id") or item.get("share_link") or apply_link or item.get("title") or "")
    # Prefer share/apply URL
    url = item.get("share_link") or apply_link or ""
    if not url and item.get("apply_options"):
        opts = item["apply_options"]
        if isinstance(opts, list) and opts:
            url = opts[0].get("link") or ""

    schedule = ext.get("schedule_type") or ""
    posted = ext.get("posted_at") or ""
    work = ext.get("work_from_home")
    job_type_hint = "Remote" if work else ""

    return {
        "jobId": job_id,
        "title": item.get("title") or "",
        "company": item.get("company_name") or "",
        "companyName": item.get("company_name") or "",
        "location": item.get("location") or location,
        "jobUrl": url,
        "postedDate": posted,
        "description": item.get("description") or "",
        "seniorityLevel": "",  # Google Jobs often omits; filters use title/description
        "employmentType": schedule,
        "workplaceType": job_type_hint,
        "source": "serpapi_google_jobs",
        "via": item.get("via") or "",
        "searchKeywords": keywords,
        "searchLocation": location,
    }
