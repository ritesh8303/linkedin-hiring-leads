import csv
from collections import Counter
from pathlib import Path

from src.filters import is_ai_related, is_fresher_friendly, is_germany_location

src = Path("data/ai_germany_fresher_jobs.csv")
with src.open(encoding="utf-8", newline="") as f:
    rows = list(csv.DictReader(f))
    fields = list(rows[0].keys()) if rows else []

kept = []
for r in rows:
    title = r.get("hiring_role") or ""
    sen = r.get("seniority") or ""
    desc = r.get("post_content") or ""
    loc = r.get("location") or ""
    if not is_germany_location(loc, "Germany"):
        continue
    if not is_ai_related(title, desc):
        continue
    if not is_fresher_friendly(title=title, seniority=sen, description=desc):
        continue
    kept.append(r)

with src.open("w", encoding="utf-8", newline="") as f:
    w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
    w.writeheader()
    w.writerows(kept)

print("before", len(rows), "after_strict", len(kept))
print("seniority", Counter((r.get("seniority") or "(blank)") for r in kept).most_common())
print("--- titles ---")
for r in kept:
    sen = (r.get("seniority") or "")[:14]
    title = (r.get("hiring_role") or "")[:60]
    company = (r.get("company") or "")[:28]
    loc = (r.get("location") or "")[:30]
    print(f"{sen:14} | {title:60} | {company:28} | {loc}")
