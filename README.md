# LinkedIn Hiring Jobs Scraper

Pulls LinkedIn jobs via Apify, filters for your search, and saves CSV.

## Live job board (GitHub Pages)

Browse the latest Germany AI fresher snapshot at:

**https://ritesh8303.github.io/linkedin-hiring-leads/**

(Source files in `docs/`.)

## Quick start

```powershell
cd C:\Users\rites\Projects\linkedin-hiring-leads
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
# add APIFY_API_TOKEN to .env
python -m src
```

Refresh the Pages dataset after a scrape:

```powershell
$env:PYTHONPATH='.'
python scripts\export_docs_jobs.py
```

Then commit and push `docs/jobs.json`.
