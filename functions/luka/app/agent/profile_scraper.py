"""Scraping del profilo LinkedIn da username, via Apify (no cookie).

Actor: apimaestro/linkedin-profile-detail  ($5 / 1000 profili).
Restituisce un dict normalizzato o None se non configurato / fallito.

NOTA sui limiti: l'API/scraper pubblico di LinkedIn NON espone l'elenco di
follower, seguiti o collegamenti di un profilo (solo i conteggi). La
navigazione della rete "amici di amici" non e' possibile senza i cookie di
sessione dell'utente. Come segnale di rete usiamo: hashtag del creator,
azienda e settore dell'esperienza corrente, sede.
"""

from __future__ import annotations

import re
from typing import Any

import httpx

from ..config import get_settings

ACTOR = "apimaestro~linkedin-profile-detail"


def extract_username(value: str) -> str:
    """Accetta 'mario-rossi', un URL completo o un URN e ritorna lo username."""
    v = (value or "").strip()
    m = re.search(r"linkedin\.com/in/([^/?#]+)", v, re.I)
    if m:
        return m.group(1)
    return v.strip("/").split("/")[-1]


def scrape_profile(username: str) -> dict[str, Any] | None:
    s = get_settings()
    if not s.apify_token:
        return None
    uname = extract_username(username)
    if not uname:
        return None
    url = f"https://api.apify.com/v2/acts/{ACTOR}/run-sync-get-dataset-items"
    try:
        with httpx.Client(timeout=180) as c:
            r = c.post(url, params={"token": s.apify_token}, json={"username": uname})
            r.raise_for_status()
            items = r.json()
    except httpx.HTTPError:
        return None
    if not isinstance(items, list) or not items:
        return None
    return _normalize(items[0], uname)


def _normalize(it: dict, uname: str) -> dict[str, Any]:
    b = it.get("basic_info") or {}
    exp = it.get("experience") or []
    cur = next((e for e in exp if e.get("is_current")), exp[0] if exp else {})

    loc = b.get("location") or {}
    location = loc.get("full") or loc.get("city") or loc.get("country") or ""

    exp_summary = "; ".join(
        f"{e.get('title', '')} @ {e.get('company', '')}".strip(" @")
        for e in exp[:5]
        if e.get("title") or e.get("company")
    )

    return {
        "username": b.get("public_identifier") or uname,
        "display_name": b.get("fullname") or b.get("first_name") or uname,
        "headline": b.get("headline") or "",
        "about": b.get("about") or "",
        "location": location,
        "industry_hint": cur.get("company") or "",
        "current_title": cur.get("title") or "",
        "hashtags": [h for h in (b.get("creator_hashtags") or []) if h],
        "experience_summary": exp_summary,
        "follower_count": b.get("follower_count"),
        "connection_count": b.get("connection_count"),
        "is_creator": bool(b.get("is_creator")),
        "profile_url": b.get("profile_url") or f"https://www.linkedin.com/in/{uname}",
        "avatar_url": b.get("profile_picture_url"),
    }


def to_raw_about(p: dict[str, Any]) -> str:
    """Costruisce un blocco testo da dare all'analisi AI dell'onboarding."""
    parts = []
    if p.get("about"):
        parts.append(p["about"])
    if p.get("experience_summary"):
        parts.append(f"Esperienze: {p['experience_summary']}")
    if p.get("location"):
        parts.append(f"Sede: {p['location']}")
    if p.get("hashtags"):
        parts.append(f"Hashtag del creator: {', '.join(p['hashtags'])}")
    if p.get("follower_count"):
        parts.append(f"Follower: {p['follower_count']}")
    return "\n".join(parts)
