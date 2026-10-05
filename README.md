# Data & AI Job Scraper

Standalone daily job board for **Data Science, ML, and AI** roles (MSc/BSc Data Science and similar).

This is a **separate repo** from [DataForge](https://github.com/ritesh8303/dataforge) (the EU job lakehouse). Keep them separate: this project is your personal apply list; DataForge is the public ATS/API pipeline.

- **Remote** → worldwide  
- **Hybrid / On-site** → EU only  

## Providers

| Provider | Role |
| --- | --- |
| LinkedIn guest | Free, primary volume (keywords rotate daily) |
| SerpAPI | Free tier backup |
| Apify | ~450 jobs/month cap (~$5 credit) |

## Setup

```powershell
cd C:\Users\rites\Projects\linkedin-hiring-leads
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
# Add SERPAPI_API_KEY and APIFY_API_TOKEN
```

## Run

```powershell
python -m src
python -m src --schedule   # daily 18:30 Europe/Berlin
.\scripts\install_windows_task.ps1   # Task: DataForgePersonalJobRadar or rename as you like
```

## Live board

https://ritesh8303.github.io/linkedin-hiring-leads/

With `auto_export_docs: true`, each run refreshes `docs/jobs.json` — commit + push to update the site.

## `.env`

```
SERPAPI_API_KEY=...
APIFY_API_TOKEN=...
```

## Architecture

See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).
