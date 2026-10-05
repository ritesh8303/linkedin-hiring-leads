from __future__ import annotations

from typing import Any

from apify_client import ApifyClient


def fetch_hiring_posts(token: str, actor_id: str, run_input: dict[str, Any]) -> list[dict[str, Any]]:
    if not token:
        raise ValueError(
            "Missing APIFY_API_TOKEN. Copy .env.example to .env and paste your token "
            "from https://console.apify.com/settings/integrations"
        )
    client = ApifyClient(token)
    run = client.actor(actor_id).call(run_input=run_input)
    if not run:
        raise RuntimeError("Apify actor returned no run metadata")
    dataset_id = _dataset_id(run)
    if not dataset_id:
        raise RuntimeError("Apify run finished without a dataset")
    return list(client.dataset(dataset_id).iterate_items())


def _dataset_id(run: Any) -> str | None:
    """Support both dict and newer typed Run objects from apify-client."""
    if isinstance(run, dict):
        return run.get("defaultDatasetId") or run.get("default_dataset_id")
    for name in ("default_dataset_id", "defaultDatasetId"):
        val = getattr(run, name, None)
        if val:
            return str(val)
    data = getattr(run, "data", None)
    if isinstance(data, dict):
        return data.get("defaultDatasetId") or data.get("default_dataset_id")
    if hasattr(run, "model_dump"):
        dumped = run.model_dump()
        return dumped.get("defaultDatasetId") or dumped.get("default_dataset_id")
    return None


def build_actor_input(cfg: dict[str, Any], keyword: str | None = None) -> dict[str, Any]:
    mode = (cfg.get("mode") or "jobs").lower()
    max_results = int(cfg.get("max_results") or 25)

    if mode == "hiring_posts":
        return {
            "hiringKeywords": cfg.get("hiring_keywords") or ["we are hiring", "looking for", "join our team"],
            "jobRoles": cfg.get("job_roles") or [],
            "keywords": cfg.get("keywords") or [],
            "locations": cfg.get("locations") or [],
            "maxResults": max_results,
            "language": "en",
            "deduplicateResults": True,
        }

    kw = keyword or cfg.get("search_keyword") or (cfg.get("job_roles") or ["Software Engineer"])[0]
    return {
        "keywords": kw,
        "location": cfg.get("location") or "Remote",
        "maxItems": max_results,
        "datePosted": cfg.get("date_posted") or "pastWeek",
        "includeDescription": True,
    }


def list_search_keywords(cfg: dict[str, Any]) -> list[str]:
    kws = cfg.get("search_keywords") or []
    if isinstance(kws, str):
        kws = [kws]
    kws = [str(k).strip() for k in kws if str(k).strip()]
    if kws:
        return kws
    single = cfg.get("search_keyword")
    if single:
        return [str(single)]
    roles = cfg.get("job_roles") or ["Software Engineer"]
    return [str(roles[0])]


def resolve_actor_id(cfg: dict[str, Any]) -> str:
    mode = (cfg.get("mode") or "jobs").lower()
    if mode == "hiring_posts":
        return cfg.get("apify_actor_hiring_posts") or cfg.get("apify_actor") or "apt_marble/linkedin-hiring-posts-scraper"
    return cfg.get("apify_actor_jobs") or cfg.get("apify_actor") or "axery/linkedin-jobs-scraper"
