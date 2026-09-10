from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx

from ..config import get_settings
from .ranking import engagement_score

_DATA = Path(__file__).resolve().parent.parent / "data" / "seed_posts.json"
_TOKEN_RE = re.compile(r"[a-z0-9]{2,}")
_TERM_STOP = {"di", "e", "the", "and", "per", "con", "in"}

# Quali region includere per ogni scelta UI.
_GEO_INCLUDE = {
    "italy": {"italy"},
    "europe": {"italy", "europe"},
    "world": {"italy", "europe", "world"},
}


@dataclass
class RawPost:
    author_name: str
    author_headline: str | None
    author_profile_url: str | None
    niche: str | None
    url: str
    text: str
    reactions: int = 0
    comments: int = 0
    reposts: int = 0
    views: int | None = None
    posted_at: datetime | None = None
    data_source: str = "sample"
    score: float = 0.0


@dataclass
class DiscoveryQuery:
    niche: str
    keywords_primary: list[str] = field(default_factory=list)
    keywords_secondary: list[str] = field(default_factory=list)
    geo: str = "italy"
    limit: int = 10


class DiscoveryProvider:
    name = "base"

    def discover(self, q: DiscoveryQuery) -> list[RawPost]:  # pragma: no cover
        raise NotImplementedError


# ───────────────────────────── Sample (gratis) ─────────────────────────────


class SampleDiscoveryProvider(DiscoveryProvider):
    """Dataset locale di post realistici. Zero costo, zero chiavi, deterministico."""

    name = "sample"

    def __init__(self) -> None:
        self._rows = json.loads(_DATA.read_text(encoding="utf-8"))

    def discover(self, q: DiscoveryQuery) -> list[RawPost]:
        wanted_regions = _GEO_INCLUDE.get(q.geo, _GEO_INCLUDE["world"])
        raw_terms = [q.niche, *q.keywords_primary, *q.keywords_secondary]
        terms: set[str] = set()
        for t in raw_terms:
            if not t or not t.strip():
                continue
            terms.add(t.strip().lower())
            # tokenizza anche i termini multi-parola ("AI B2B / Sales" -> ai, b2b, sales)
            for word in _TOKEN_RE.findall(t.lower()):
                if len(word) >= 2 and word not in _TERM_STOP:
                    terms.add(word)

        out: list[RawPost] = []
        for row in self._rows:
            if row.get("region") not in wanted_regions:
                continue
            haystack = " ".join(
                [
                    row.get("text", ""),
                    row.get("niche", ""),
                    " ".join(row.get("keywords", [])),
                ]
            ).lower()
            matched = [t for t in terms if t in haystack]
            # Se l'utente non ha dato termini, restituisci tutto il bacino.
            if terms and not matched:
                continue

            posted_at = datetime.now(timezone.utc) - timedelta(
                days=row.get("posted_days_ago", 5)
            )
            base = engagement_score(
                views=row.get("views"),
                reactions=row.get("reactions", 0),
                comments=row.get("comments", 0),
                reposts=row.get("reposts", 0),
                posted_at=posted_at,
            )
            # Boost per pertinenza semantica rispetto alla query.
            relevance = 1.0 + 0.12 * len(matched) if terms else 1.0

            out.append(
                RawPost(
                    author_name=row["author_name"],
                    author_headline=row.get("author_headline"),
                    author_profile_url=row.get("author_profile_url"),
                    niche=row.get("niche"),
                    url=row["url"],
                    text=row["text"],
                    reactions=row.get("reactions", 0),
                    comments=row.get("comments", 0),
                    reposts=row.get("reposts", 0),
                    views=row.get("views"),
                    posted_at=posted_at,
                    data_source="sample",
                    score=round(base * relevance, 4),
                )
            )

        out.sort(key=lambda p: p.score, reverse=True)
        return out[: q.limit]


# ───────────────────────── Apify (reale, opzionale) ─────────────────────────


class ApifyDiscoveryProvider(DiscoveryProvider):
    """Scraping reale via Apify actor. Richiede APIFY_TOKEN. Consuma crediti.

    Default: `apimaestro/linkedin-posts-search-scraper-no-cookies`
    (ricerca per keyword, nessun cookie LinkedIn necessario).
    Input: keyword, sort_type ("relevance"|"date_posted"), date_filter, limit (<=50).
    L'estrazione dei campi e' difensiva: gli scraper cambiano spesso i nomi
    delle chiavi in output.
    """

    name = "apify"
    # geo -> valore date_filter dell'actor (piu' recente = piu' pertinente per nicchia)
    _DATE_FILTER = {"italy": "past-month", "europe": "past-month", "world": "past-week"}

    def __init__(self, token: str, actor: str) -> None:
        self.token = token
        self.actor_path = actor.replace("/", "~")

    def discover(self, q: DiscoveryQuery) -> list[RawPost]:
        keyword = " ".join([q.niche, *q.keywords_primary[:3]]).strip()
        payload = {
            "keyword": keyword,
            "sort_type": "relevance",
            "date_filter": self._DATE_FILTER.get(q.geo, ""),
            "limit": min(max(q.limit * 3, 10), 50),
            "total_posts": min(max(q.limit * 3, 10), 50),
        }
        url = (
            f"https://api.apify.com/v2/acts/{self.actor_path}"
            "/run-sync-get-dataset-items"
        )
        with httpx.Client(timeout=180) as client:
            r = client.post(url, params={"token": self.token}, json=payload)
            r.raise_for_status()
            items = r.json()

        geo_terms = _GEO_TEXT_HINTS.get(q.geo, set())
        out: list[RawPost] = []
        for it in items if isinstance(items, list) else []:
            text = _dig(it, "text", "postText", "content", "post_text", "commentary") or ""
            link = _dig(it, "url", "postUrl", "post_url", "link", "permalink") or ""
            if not text.strip() or not link:
                continue
            reactions = _num(it, "numLikes", "likesCount", "reactionsCount", "reactions",
                              "likes", "num_reactions", "totalReactionCount")
            comments = _num(it, "numComments", "commentsCount", "comments", "num_comments")
            reposts = _num(it, "numShares", "sharesCount", "repostsCount", "reposts",
                           "shares", "num_reposts")
            views = _num(it, "numViews", "viewsCount", "views", "impressions") or None
            posted_at = _parse_dt(
                _dig(it, "postedAtISO", "publishedAt", "post_date", "date",
                     "posted_at", "time")
            )
            author = (
                _dig(it, "authorName", "author_name", "authorFullName")
                or _dig(it.get("author") or {}, "name", "fullName")
                or _dig(it.get("actor") or {}, "name")
                or "Autore LinkedIn"
            )
            headline = (
                _dig(it, "authorHeadline", "author_headline", "authorTitle",
                     "authorSubtitle")
                or _dig(it.get("author") or {}, "headline", "occupation")
            )
            profile_url = (
                _dig(it, "authorProfileUrl", "author_url", "authorUrl", "profileUrl")
                or _dig(it.get("author") or {}, "url", "profileUrl")
            )

            # filtro geografico best-effort sul testo/headline
            if geo_terms:
                hay = f"{text} {headline or ''} {profile_url or ''}".lower()
                if not any(t in hay for t in geo_terms):
                    # non scartare del tutto: penalizza in ranking
                    geo_penalty = 0.6
                else:
                    geo_penalty = 1.0
            else:
                geo_penalty = 1.0

            score = engagement_score(
                views=views,
                reactions=reactions,
                comments=comments,
                reposts=reposts,
                posted_at=posted_at,
            )
            out.append(
                RawPost(
                    author_name=author,
                    author_headline=headline,
                    author_profile_url=profile_url,
                    niche=q.niche,
                    url=link,
                    text=text.strip(),
                    reactions=reactions,
                    comments=comments,
                    reposts=reposts,
                    views=views,
                    posted_at=posted_at,
                    data_source="apify",
                    score=round(score * geo_penalty, 4),
                )
            )

        out.sort(key=lambda p: p.score, reverse=True)
        return out[: q.limit]


_GEO_TEXT_HINTS = {
    "italy": {"italia", "italy", "milano", "roma", "torino", " it ", "italian"},
    "europe": {"europe", "europa", "eu ", "london", "berlin", "paris", "madrid",
               "amsterdam", "italia", "italy"},
}


def _dig(obj: dict, *keys: str) -> str | None:
    if not isinstance(obj, dict):
        return None
    for k in keys:
        v = obj.get(k)
        if isinstance(v, str) and v.strip():
            return v
    return None


def _num(obj: dict, *keys: str) -> int:
    if not isinstance(obj, dict):
        return 0
    for k in keys:
        v = obj.get(k)
        if isinstance(v, (int, float)):
            return int(v)
        if isinstance(v, str) and v.replace(",", "").replace(".", "").isdigit():
            return int(v.replace(",", "").replace(".", ""))
    return 0


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def get_provider() -> DiscoveryProvider:
    s = get_settings()
    if s.has_apify:
        return ApifyDiscoveryProvider(s.apify_token, s.apify_actor)  # type: ignore[arg-type]
    return SampleDiscoveryProvider()
