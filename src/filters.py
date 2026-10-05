"""Text normalization and qualification filters (mirrors the n8n template logic)."""

from __future__ import annotations

import re
import unicodedata
from typing import Iterable

# Mathematical bold/italic and other styled unicode letters → ASCII
_MATH_ALPHA = {}
# Bold A-Z (U+1D400–U+1D419), bold a-z (U+1D41A–U+1D433)
for i, ch in enumerate("ABCDEFGHIJKLMNOPQRSTUVWXYZ"):
    _MATH_ALPHA[0x1D400 + i] = ch
    _MATH_ALPHA[0x1D41A + i] = ch.lower()
# Italic A-Z / a-z
for i, ch in enumerate("ABCDEFGHIJKLMNOPQRSTUVWXYZ"):
    _MATH_ALPHA[0x1D434 + i] = ch
    _MATH_ALPHA[0x1D44E + i] = ch.lower()
# Bold italic
for i, ch in enumerate("ABCDEFGHIJKLMNOPQRSTUVWXYZ"):
    _MATH_ALPHA[0x1D468 + i] = ch
    _MATH_ALPHA[0x1D482 + i] = ch.lower()
# Sans-serif bold
for i, ch in enumerate("ABCDEFGHIJKLMNOPQRSTUVWXYZ"):
    _MATH_ALPHA[0x1D5D4 + i] = ch
    _MATH_ALPHA[0x1D5EE + i] = ch.lower()
# Sans-serif bold italic
for i, ch in enumerate("ABCDEFGHIJKLMNOPQRSTUVWXYZ"):
    _MATH_ALPHA[0x1D63C + i] = ch
    _MATH_ALPHA[0x1D656 + i] = ch.lower()


def normalize_linkedin_text(text: str) -> str:
    if not text:
        return ""
    chars = []
    for ch in text:
        mapped = _MATH_ALPHA.get(ord(ch))
        if mapped is not None:
            chars.append(mapped)
        else:
            chars.append(ch)
    out = "".join(chars)
    out = unicodedata.normalize("NFKC", out)
    return out


NOISE_PHRASES = [
    "how to",
    "tips for",
    "tip:",
    "lesson learned",
    "i built",
    "i launched",
    "check out my",
    "proud to announce my",
    "webinar",
    "workshop",
    "masterclass",
    "tutorial",
    "case study",
    "thread",
    "like if you agree",
    "comment below",
    "repost if",
    "follow for more",
    "newsletter",
    "subscribe",
    "ebook",
    "free guide",
    "carousel",
    "infographic",
    "conference",
    "speaking at",
    "podcast episode",
]

JOB_SEEKER_PHRASES = [
    "hire me",
    "hiring me",
    "open to work",
    "opentowork",
    "#opentowork",
    "looking for a job",
    "looking for opportunities",
    "looking for my next",
    "seeking opportunities",
    "seeking a new role",
    "available for hire",
    "actively looking",
    "job search",
    "please refer me",
    "referral appreciated",
    "i am looking for",
    "i'm looking for a role",
    "i'm looking for a position",
    "resume attached",
    "cv attached",
]

HIRING_PHRASES = [
    "we're hiring",
    "we are hiring",
    "we are looking for",
    "we're looking for",
    "now hiring",
    "currently hiring",
    "urgently hiring",
    "hiring immediately",
    "join our team",
    "join the team",
    "open position",
    "open positions",
    "open role",
    "open roles",
    "job opening",
    "job openings",
    "role opening",
    "new opening",
    "vacancy",
    "vacancies",
    "apply now",
    "apply here",
    "send your resume",
    "send your cv",
    "send me your",
    "dm me your resume",
    "drop your resume",
    "interested candidates",
    "candidates wanted",
    "looking to hire",
    "looking for a",
    "looking for an",
    "hiring a",
    "hiring an",
    "hiring for",
    "expanding the team",
    "growing our team",
    "immediate joiner",
    "immediate joiners",
    "full-time opening",
    "full time opening",
]

EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")
PHONE_RE = re.compile(r"(?:\+|00)?[\d][\d\s\-().]{7,}\d")
WHATSAPP_RE = re.compile(r"(?:https?://)?(?:wa\.me|api\.whatsapp\.com)/\S+", re.I)
APPLY_LINK_RE = re.compile(r"https?://(?:lnkd\.in|linkedin\.com|bit\.ly|forms\.gle|docs\.google\.com)/\S+", re.I)


def _contains_any(text: str, phrases: Iterable[str]) -> bool:
    return any(p in text for p in phrases)


def is_noise(text: str) -> bool:
    return _contains_any(text, NOISE_PHRASES)


def is_job_seeker(text: str) -> bool:
    return _contains_any(text, JOB_SEEKER_PHRASES)


def has_hiring_intent(text: str) -> bool:
    return _contains_any(text, HIRING_PHRASES)


def matches_job_search(text: str, job_roles: list[str], keywords: list[str] | None = None) -> bool:
    """Keep posts that mention at least one target role.

    Keywords are optional boosters: if provided and none match, still keep
    when a role matches (role is the primary signal for job search).
    """
    roles = [r.lower().strip() for r in job_roles if r and r.strip()]
    if not roles:
        return True
    if any(role in text for role in roles):
        return True
    # Also allow partial title tokens for multi-word roles (e.g. "backend" from Backend Engineer)
    for role in roles:
        tokens = [t for t in role.split() if len(t) > 3 and t not in {"with", "from", "senior", "junior"}]
        if len(tokens) >= 2 and all(t in text for t in tokens):
            return True
    return False


def detect_job_type(text: str) -> str:
    if "hybrid" in text:
        return "Hybrid"
    if "remote" in text or "work from home" in text or "wfh" in text:
        return "Remote"
    if "on-site" in text or "onsite" in text or "in-office" in text or "office based" in text:
        return "On-Site"
    return "Unknown"


def extract_contacts(text: str) -> dict[str, str]:
    emails = EMAIL_RE.findall(text)
    phones = PHONE_RE.findall(text)
    whatsapp = WHATSAPP_RE.findall(text)
    apply_links = APPLY_LINK_RE.findall(text)
    return {
        "email": emails[0] if emails else "",
        "phone": phones[0].strip() if phones else "",
        "whatsapp": whatsapp[0] if whatsapp else "",
        "apply_link": apply_links[0] if apply_links else "",
    }


GERMANY_TOKENS = [
    "germany",
    "deutschland",
    "berlin",
    "munich",
    "münchen",
    "muenchen",
    "hamburg",
    "frankfurt",
    "cologne",
    "köln",
    "koeln",
    "stuttgart",
    "düsseldorf",
    "duesseldorf",
    "leipzig",
    "dresden",
    "nürnberg",
    "nuernberg",
    "hannover",
    "bremen",
    "dortmund",
    "essen",
    "karlsruhe",
    "mannheim",
    "freiburg",
    "aachen",
    "bonn",
    "heidelberg",
    "potsdam",
    "nrw",
    "bavaria",
    "bayern",
]

ENTRY_SENIORITY = {
    "entry level",
    "entry-level",
    "internship",
    "intern",
}

SENIOR_SENIORITY = {
    "mid-senior level",
    "mid senior level",
    "director",
    "executive",
    "owner",
    "partner",
}

FRESHER_POSITIVE = [
    "entry level",
    "entry-level",
    "no experience",
    "no prior experience",
    "without experience",
    "0 years",
    "0+ years",
    "0-1 years",
    "0–1 years",
    "fresher",
    "freshers",
    "graduate",
    "new graduate",
    "recent graduate",
    "junior",
    "trainee",
    "internship",
    "intern ",
    "working student",
    "werkstudent",
    "berufseinsteiger",
    "berufseinsteigerin",
    "absolvent",
    "absolventin",
    "ohne berufserfahrung",
    "keine berufserfahrung",
    "einstiegsposition",
    "einstieg ",
    "praktikum",
    "praktikant",
    "junior engineer",
    "junior developer",
    "university graduate",
]

EXPERIENCED_NEGATIVE = [
    "mid-senior",
    "senior ",
    " sr.",
    "staff engineer",
    "principal ",
    "lead engineer",
    "team lead",
    "5+ years",
    "5 years",
    "4+ years",
    "3+ years",
    "3 years of experience",
    "2+ years",
    "mindestens 3",
    "mindestens 2 jahre",
    "mehrjährige erfahrung",
    "several years of experience",
    "extensive experience",
    "proven experience",
    "erfahrener",
    "erfahrene ",
    "mit berufserfahrung",
    "phd",
    "ph.d",
    "doktorand",
    "doctoral",
    "postdoc",
    "postdoctoral",
    "promotion -",
    "research associate",
]


def is_germany_location(location: str, search_location: str = "") -> bool:
    hay = f"{location} {search_location}".lower()
    if not hay.strip():
        return False
    if "remote" in hay and any(t in hay for t in ("germany", "deutschland", "berlin", "munich", "münchen")):
        return True
    return any(tok in hay for tok in GERMANY_TOKENS)


def is_fresher_friendly(
    *,
    title: str,
    seniority: str,
    description: str,
) -> bool:
    title_l = (title or "").lower()
    sen = (seniority or "").lower().strip()
    desc = (description or "").lower()

    title_fresher = bool(
        re.search(
            r"\b(junior|intern|internship|trainee|werkstudent|working student|graduate|berufseinsteiger|"
            r"praktikum|praktikant|entry|duales studium|absolvent|fellow)\b",
            title_l,
        )
    )

    # Hard reject research/senior tracks that are not fresher jobs
    if re.search(
        r"\b(senior|staff|principal|lead|head of|director|erfahrener|erfahrene|phd|doktorand|doctoral|postdoc|postdoctoral)\b",
        title_l,
    ):
        return False

    if sen in SENIOR_SENIORITY:
        return False

    if sen in ENTRY_SENIORITY or sen.startswith("entry"):
        if any(neg in desc for neg in ("5+ years", "5 years", "4+ years", "3+ years", "mindestens 3", "erfahrener")):
            if not title_fresher:
                return False
        return True

    # Not Applicable / Associate / blank: only keep with clear fresher title signals
    if title_fresher:
        return True

    return False


def is_ai_related(title: str, description: str, roles: list[str] | None = None) -> bool:
    hay = f"{title} {description}".lower()
    ai_tokens = [
        "artificial intelligence",
        "machine learning",
        " deep learning",
        "generative ai",
        " genai",
        " llm",
        "nlp",
        "computer vision",
        " neural",
        "ki-",
        " ki ",
        "ki engineer",
        "ml engineer",
        "ai engineer",
        "data scientist",
        "mlops",
        "foundation model",
    ]
    if any(t in hay for t in ai_tokens):
        return True
    for role in roles or []:
        if role and role.lower() in hay:
            return True
    # bare "ai" as word
    return bool(re.search(r"\bai\b", hay))


def qualify_post(
    raw_text: str,
    job_roles: list[str],
    keywords: list[str] | None = None,
    *,
    require_hiring_phrase: bool = True,
) -> tuple[bool, str, str]:
    """Return (ok, reason, normalized_text)."""
    text = normalize_linkedin_text(raw_text).lower()
    if not text.strip():
        return False, "empty", text
    if is_noise(text):
        return False, "noise", text
    if is_job_seeker(text):
        return False, "job_seeker", text
    if require_hiring_phrase and not has_hiring_intent(text):
        return False, "no_hiring_intent", text
    if not matches_job_search(text, job_roles, keywords):
        return False, "role_mismatch", text
    return True, "ok", text
