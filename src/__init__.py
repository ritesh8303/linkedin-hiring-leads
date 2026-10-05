"""LinkedIn hiring-post job search scraper.

Fetches public LinkedIn hiring posts via Apify, filters for real openings
matching your target roles, dedupes across runs, and saves to CSV
(and optionally Google Sheets).
"""

__version__ = "1.0.0"
