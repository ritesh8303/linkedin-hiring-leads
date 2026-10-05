# Public ATS coverage (local personal radar)

This project polls **public, unauthenticated** ATS / career feeds only.

## Included (no API key)

| ATS | How | Config |
|-----|-----|--------|
| Greenhouse | `boards-api.greenhouse.io` | `config/ats_boards.yaml` → `greenhouse` |
| Ashby | posting-api job board | `ashby` |
| Lever | `api.lever.co/v0/postings` | `lever` |
| SmartRecruiters | company postings API | `smartrecruiters` |
| Workable | widget accounts API | `workable` |
| Recruitee | `{slug}.recruitee.com/api/offers` | `recruitee` |
| Personio | public XML career feed | `config/personio_tenants.json` |
| Pinpoint | `{slug}.pinpointhq.com/postings.json` | `pinpoint` |
| Teamtailor | `{host}/jobs.rss` | `teamtailor` |
| Comeet | careers-api positions | `comeet` |
| Workday CXS | public `wday/cxs/.../jobs` POST | `config/workday_targets.yaml` |

Boards are **rotated daily** so a large list is covered over about a week without hammering every company every run.

## Not included (require private tokens / partner access)

These may have “public careers pages” but **not** a free open jobs API for scrapers:

- Softgarden (Bearer token + channel ID)
- BambooHR ATS API (authenticated)
- Jobvite / iCIMS / Taleo / SuccessFactors / Phenom (partner or login)
- Most custom/corporate career sites with no documented feed

## Reality check

“Every ATS company in the world” is impossible: new tenants appear daily, and many boards 404 or return empty. We keep **every major public ATS protocol** wired, with growing board/tenant lists. Dead tokens are pruned when discovered.

Rebuild board seeds (optional):

```powershell
python scripts/build_ats_boards.py
```
