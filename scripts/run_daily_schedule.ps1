# Run daily job scrape at 18:30 (Europe/Berlin) — fresh jobs before ~8 PM applications
Set-Location $PSScriptRoot\..

$env:PYTHONIOENCODING = "utf-8"
.\.venv\Scripts\python.exe -m src --schedule
