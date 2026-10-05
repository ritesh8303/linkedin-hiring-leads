# Data & AI Job Radar

Personal job board for **Data Science, Machine Learning, and AI** roles — remote worldwide, hybrid/on-site in the EU.

**Live board:** [ritesh8303.github.io/linkedin-hiring-leads](https://ritesh8303.github.io/linkedin-hiring-leads/)

> Standalone project (personal apply list). Not part of the [DataForge](https://github.com/ritesh8303/dataforge) lakehouse.

---

## Features

- **Multi-source scrape** — LinkedIn guest (free), SerpAPI Google Jobs, Apify (budget-capped)
- **Smart filters** — Data/AI titles; remote worldwide; hybrid & on-site limited to the EU
- **Deduped storage** — CSV + SQLite; optional Google Sheets
- **Static job board** — GitHub Pages UI with search and filters
- **Local dashboard** — one-click **Run scrape** with live pipeline logs → **Ready to apply**

## Architecture

```
Your PC                         GitHub Pages
────────                        ────────────
python -m src [--dashboard]  →  docs/jobs.json
  ├─ LinkedIn guest             (board UI)
  ├─ SerpAPI (Google Jobs)
  └─ Apify (capped ~450/mo)
```

Details: [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)

## Quick start

```powershell
git clone https://github.com/ritesh8303/linkedin-hiring-leads.git
cd linkedin-hiring-leads
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
```

Add to `.env`:

```
SERPAPI_API_KEY=your_key
APIFY_API_TOKEN=your_token
```

### Scrape once (CLI)

```powershell
python -m src
```

### Local board + Run button

```powershell
python -m src --dashboard
```

Open [http://127.0.0.1:8787/](http://127.0.0.1:8787/) → **Run scrape**.  
Live logs show each provider → filter → save → export. When finished: **Ready to apply**.

### Daily schedule (optional)

```powershell
python -m src --schedule
# or
.\scripts\install_windows_task.ps1
```

Default: **18:30 Europe/Berlin**.

## Configuration

Edit [`config.yaml`](config.yaml):

| Setting | Purpose |
| --- | --- |
| `providers` | `linkedin_guest`, `serpapi`, `apify` |
| `search_keywords` | Roles to rotate daily |
| `location_policy` | `remote_worldwide_eu_hybrid_onsite` |
| `apify_monthly_job_budget` | Default `450` (~$5/mo) |
| `schedule.time` | Daily run time |
| `auto_export_docs` | Refresh `docs/jobs.json` after each run |

## Publishing the board

GitHub Pages is served from `/docs` on `master`.

After a scrape (with `auto_export_docs: true`):

```powershell
git add docs/jobs.json
git commit -m "Refresh job board snapshot"
git push origin master
```

Site: **https://ritesh8303.github.io/linkedin-hiring-leads/**

> The public Pages site is a **static snapshot**. The **Run scrape** button only works when the local dashboard is running (`python -m src --dashboard`).

## Project layout

```
├── config.yaml          # Providers, keywords, schedule
├── src/                 # Scrape pipeline + local dashboard
├── scripts/             # Export, Windows task, schedule helper
├── docs/                # GitHub Pages board (HTML/CSS/JS + jobs.json)
├── data/                # CSV + SQLite (gitignored)
└── .env                 # API keys (gitignored)
```

## License

Personal / portfolio use. Respect LinkedIn, SerpAPI, and Apify terms of service. Verify every posting on the source site before applying.
