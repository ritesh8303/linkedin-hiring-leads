# Where this runs (architecture)

There is **no separate cloud backend server**. Everything is a **local Python job** on your PC, plus a static website on GitHub Pages.

```
 YOUR PC (the real "backend")
 ┌─────────────────────────────────────────────────────────────┐
 │  Windows Task Scheduler  →  daily 18:30                     │
 │           │                                                 │
 │           ▼                                                 │
 │  python -m src   (src/main.py)                              │
 │           │                                                 │
 │           ├─► LinkedIn guest HTTP   (free)                  │
 │           ├─► SerpAPI Google Jobs   (free tier)             │
 │           └─► Apify actor           (~$5/mo budget)         │
 │           │                                                 │
 │           ▼                                                 │
 │  filters (Data/AI + Remote world / EU hybrid-onsite)        │
 │           │                                                 │
 │           ▼                                                 │
 │  data/data_ai_remote_eu_jobs.csv   + SQLite dedupe DB       │
 │           │                                                 │
 │           ▼                                                 │
 │  docs/jobs.json  (auto-export)                              │
 └─────────────────────────────────────────────────────────────┘
           │  git push (optional)
           ▼
 GitHub Pages  →  https://ritesh8303.github.io/linkedin-hiring-leads/
 (frontend only — reads jobs.json in the browser)
```

## Key files

| Path | Role |
| --- | --- |
| `src/main.py` | Entry point + schedule loop |
| `src/providers.py` | Calls LinkedIn / SerpAPI / Apify |
| `src/filters.py` + `src/enrich.py` | Data/AI + location rules |
| `src/apify_budget.py` | Caps Apify ~450 jobs/month |
| `config.yaml` | Keywords, providers, 18:30 schedule |
| `.env` | API keys (never committed) |
| `data/*.csv` | Scraped jobs |
| `docs/` | Static site for GitHub Pages |

## When it runs

- **Windows task:** `LinkedInDataAIJobScrape` every day at **18:30**
- PC must be **on** at that time (or wake / StartWhenAvailable)
- You apply after **~20:00** using the CSV or the GitHub Pages site
