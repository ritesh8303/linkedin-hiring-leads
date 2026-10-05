from __future__ import annotations

from typing import Any

from .filters import (
    allows_location_policy,
    detect_job_type,
    extract_contacts,
    is_data_ai_sector,
    is_fresher_friendly,
    is_germany_location,
    normalize_linkedin_text,
    qualify_post,
)
from .storage import fingerprint


def post_text(item: dict[str, Any]) -> str:
    for key in (
        "description",
        "jobDescription",
        "postSnippet",
        "post_content",
        "text",
        "content",
        "commentary",
        "postText",
        "snippet",
        "title",
    ):
        val = item.get(key)
        if isinstance(val, str) and val.strip():
            return val
    title = item.get("title") or item.get("jobTitle") or ""
    company = item.get("companyName") or item.get("company") or ""
    loc = item.get("location") or ""
    return " | ".join(str(x) for x in (title, company, loc) if x)


def post_url(item: dict[str, Any]) -> str:
    for key in ("jobUrl", "url", "link", "postUrl", "post_url", "applyUrl"):
        val = item.get(key)
        if isinstance(val, str) and val.strip():
            return val
    return ""


def post_id_for(item: dict[str, Any], text: str, url: str) -> str:
    for key in ("jobId", "id", "postId", "post_id", "urn"):
        val = item.get(key)
        if isinstance(val, str) and val.strip():
            return val
        if isinstance(val, (int, float)):
            return str(val)
    if "activity-" in url:
        return url.split("activity-")[-1].split("?")[0].rstrip("/")
    if "/view/" in url:
        return url.split("/view/")[-1].split("?")[0].rstrip("/")
    return fingerprint(text, url)


def enrich_item(
    item: dict[str, Any],
    job_roles: list[str],
    keywords: list[str] | None = None,
    *,
    mode: str = "jobs",
    entry_level_only: bool = False,
    require_germany: bool = False,
    location_policy: str = "",
    search_location: str = "",
    require_ai: bool = False,
    require_data_ai: bool = False,
) -> dict[str, Any] | None:
    text = post_text(item)
    url = post_url(item)
    title = str(item.get("title") or item.get("jobTitle") or item.get("hiringRole") or "")
    company = str(
        item.get("companyName")
        or item.get("company")
        or item.get("hiringCompany")
        or ""
    )
    location = str(item.get("location") or "")
    seniority = str(item.get("seniorityLevel") or item.get("seniority") or "")
    search_loc = str(item.get("searchLocation") or search_location or "")

    blob = normalize_linkedin_text(" ".join([title, company, location, text]))

    if mode == "hiring_posts":
        ok, reason, normalized = qualify_post(
            text,
            job_roles,
            keywords,
            require_hiring_phrase=False,
        )
        if not ok and reason in {"noise", "job_seeker", "role_mismatch", "empty"}:
            return None
    else:
        normalized = blob.lower()
        reason = "ok"
        if not (title or text).strip():
            return None

    author_url = item.get("authorProfileUrl") or item.get("companyUrl") or item.get("author_linkedin") or ""
    workplace = str(item.get("workplaceType") or item.get("workType") or location)
    job_type = detect_job_type(normalize_linkedin_text(f"{workplace} {blob}").lower())

    if require_germany:
        if not location or not is_germany_location(location):
            return None

    policy = (location_policy or "").strip().lower()
    if policy in {"remote_world_eu_local", "remote_worldwide_eu_hybrid_onsite"}:
        if not allows_location_policy(job_type=job_type, location=location, description=text):
            return None

    if (require_data_ai or require_ai) and not is_data_ai_sector(title, text, job_roles):
        return None

    if entry_level_only and not is_fresher_friendly(title=title, seniority=seniority, description=text):
        return None

    contacts = extract_contacts(normalize_linkedin_text(text))
    author = (
        item.get("recruiterName")
        or item.get("authorName")
        or item.get("author_name")
        or item.get("poster")
        or ""
    )
    published = (
        item.get("postedAt")
        or item.get("postedDate")
        or item.get("postDate")
        or item.get("published_date")
        or item.get("timestamp")
        or ""
    )
    return {
        "post_id": post_id_for(item, text, url),
        "published_date": published,
        "job_type": job_type,
        "hiring_role": title or item.get("hiringRole") or item.get("jobRoleMatched") or "",
        "company": company,
        "author_name": author if isinstance(author, str) else str(author),
        "author_linkedin": author_url,
        "post_url": url,
        "post_content": normalize_linkedin_text(text)[:5000],
        "email": contacts["email"],
        "phone": contacts["phone"],
        "whatsapp": contacts["whatsapp"],
        "apply_link": contacts["apply_link"] or url,
        "hiring_intent": item.get("hiringIntent") or item.get("employmentType") or "",
        "seniority": seniority,
        "location": location,
        "_filter_reason": reason,
        "_location": location,
    }
