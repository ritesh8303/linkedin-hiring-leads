# Where this runs (architecture)

There is **no separate cloud backend server**. Everything is a **local Python job** on your PC, plus a static website on GitHub Pages.

```
 YOUR PC (the real "backend")
 ┌─────────────────────────────────────────────────────────────┐
 │  Windows Task Scheduler  →  daily 18:30                     │
 │           │                                                 │
 │           ▼                                                 │
 │  python -m src / --dashboard                                │
 │           │                                                 │
 │           ├─► Arbeitnow / Remotive / Himalayas / BA API     │
 │           ├─► Greenhouse + Ashby + Lever (rotated boards)   │
 │           ├─► LinkedIn guest HTTP   (free)                  │
 │           ├─► SerpAPI Google Jobs   (free tier)             │
 │           └─► Apify actor           (~$5/mo budget)         │
 │           │                                                 │
 │           ▼                                                 │
 │  filters (Data/AI/cloud + Remote world / EU hybrid-onsite)  │
 │           │                                                 │
 │           ▼                                                 │
 │  SQLite dedupe (id + URL + company|title|location)          │
 │  data/*.csv  →  docs/jobs.json                              │
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
| `src/dashboard.py` | Local UI server + Run scrape API (SSE logs) |

## Local dashboard (button + live logs)

```
Browser  http://127.0.0.1:8787/
   │
   ├─ POST /api/run     → starts python pipeline on this PC
   ├─ GET  /api/events  → live SSE log (providers → filter → save)
   └─ GET  /jobs.json   → board reload when status = Ready to apply
```

Start with: `python -m src --dashboard`

GitHub Pages is still a static snapshot only — the **Run scrape** button needs this local process.

## When it runs

- **On demand:** open local dashboard → **Run scrape** → wait for **Ready to apply**
- **Windows task:** `DataForgePersonalJobRadar` (or older name) daily at **18:30**
- PC must be **on** (or wake / StartWhenAvailable)
- You apply after **~20:00** using the board or CSV
