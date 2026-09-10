from __future__ import annotations

import html
import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import httpx

from ..config import get_settings
from .ranking import engagement_score

_DATA = Path(__file__).resolve().parent.parent / "data" / "seed_posts.json"
_TOKEN_RE = re.compile(r"[a-z0-9]{2,}")
_TERM_STOP = {"di", "e", "the", "and", "per", "con", "in"}
_TAG_RE = re.compile(r"<[^>]+>")


def _clean_html(text: str) -> str:
    return html.unescape(_TAG_RE.sub("", text or "")).strip()

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
        words: list[str] = []
        for term in [q.niche, *q.keywords_primary]:
            for w in _TOKEN_RE.findall((term or "").lower()):
                if w not in _TERM_STOP and w not in words:
                    words.append(w)
        keyword = " ".join(words[:5]) or (q.niche or "b2b")
        want = min(max(q.limit * 3, 10), 50)
        payload = {
            "keyword": keyword,
            "sort_type": "relevance",
            "limit": want,
            "total_posts": want,
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
            if not isinstance(it, dict):
                continue
            author = it.get("author") if isinstance(it.get("author"), dict) else {}
            stats = it.get("stats") if isinstance(it.get("stats"), dict) else {}

            text = (_dig(it, "text", "postText", "content", "commentary") or "").strip()
            link = _dig(it, "post_url", "url", "postUrl", "link", "permalink") or ""
            if not text or not link:
                continue

            reactions = _num(stats, "total_reactions", "reactions_count", "likes") or _num(
                it, "numLikes", "likesCount", "totalReactionCount"
            )
            comments = _num(stats, "comments", "comments_count") or _num(
                it, "numComments", "commentsCount"
            )
            reposts = _num(stats, "shares", "reposts", "shares_count") or _num(
                it, "numShares", "sharesCount"
            )
            views = _num(stats, "views", "impressions") or _num(it, "numViews", "views")
            if not views:
                # l'actor non espone le views: stima da engagement per il ranking
                views = (reactions + 4 * comments + 8 * reposts) * 25 or None

            posted_raw = it.get("posted_at")
            if isinstance(posted_raw, dict):
                posted_at = _parse_dt(posted_raw.get("date")) or _parse_ts(
                    posted_raw.get("timestamp")
                )
            else:
                posted_at = _parse_dt(
                    _dig(it, "postedAtISO", "publishedAt", "date", "time")
                )

            name = _dig(author, "name", "full_name", "fullName") or _dig(
                it, "authorName", "author_name"
            ) or "Autore LinkedIn"
            headline = _dig(author, "headline", "occupation", "subtitle")
            profile_url = _dig(author, "profile_url", "url", "profileUrl")

            geo_penalty = 1.0
            if geo_terms:
                hay = f"{text} {headline or ''} {profile_url or ''}".lower()
                if not any(t in hay for t in geo_terms):
                    geo_penalty = 0.7

            score = engagement_score(
                views=views, reactions=reactions, comments=comments,
                reposts=reposts, posted_at=posted_at,
            )
            out.append(
                RawPost(
                    author_name=name,
                    author_headline=headline,
                    author_profile_url=profile_url,
                    niche=q.niche,
                    url=link,
                    text=text,
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


def _parse_ts(value: Any) -> datetime | None:
    try:
        ts = float(value)
    except (TypeError, ValueError):
        return None
    if ts > 1e12:  # millisecondi
        ts /= 1000.0
    try:
        return datetime.fromtimestamp(ts, tz=timezone.utc)
    except (OverflowError, OSError, ValueError):
        return None


# ─────────────────── Free (Hacker News + Reddit, zero chiavi) ───────────────────


class FreeDiscoveryProvider(DiscoveryProvider):
    """Segnale di nicchia 100% gratuito, senza account nè API key.

    NON sono post LinkedIn: sono i contenuti che stanno performando ORA sulla
    stessa nicchia su Hacker News (Algolia API, nessuna auth) e Reddit (JSON
    pubblico). Servono a Luka per cavalcare un trend reale. Per i post
    LinkedIn veri: provider "apify" (a pagamento) o incolla-post manuale.

    Se la rete non risponde, ricade sul dataset locale.
    """

    name = "free"
    HN_URL = "https://hn.algolia.com/api/v1/search"
    _SUBREDDITS = [
        "sales", "marketing", "Entrepreneur", "startups", "SaaS",
        "artificial", "personalbranding", "B2BMarketing", "smallbusiness",
        "digital_marketing", "growmybusiness",
    ]
    _WINDOW = {"italy": "past-month", "europe": "past-month", "world": "past-week"}

    def discover(self, q: DiscoveryQuery) -> list[RawPost]:
        # Algolia/Reddit rendono meglio con query brevi: max ~5 parole chiave.
        words: list[str] = []
        for term in [q.niche, *q.keywords_primary, *q.keywords_secondary]:
            for w in _TOKEN_RE.findall((term or "").lower()):
                if w not in _TERM_STOP and w not in words:
                    words.append(w)
        query = " ".join(words[:5]) or (q.niche or "b2b")

        out: list[RawPost] = []
        try:
            out.extend(self._hacker_news(query, q))
        except Exception:  # noqa: BLE001
            pass
        try:
            out.extend(self._reddit(query, q))
        except Exception:  # noqa: BLE001
            pass

        # dedup per url, ordina per score
        seen: set[str] = set()
        deduped = []
        for p in sorted(out, key=lambda x: x.score, reverse=True):
            if p.url in seen:
                continue
            seen.add(p.url)
            deduped.append(p)

        if not deduped:
            return SampleDiscoveryProvider().discover(q)
        return deduped[: q.limit]

    def _hacker_news(self, query: str, q: DiscoveryQuery) -> list[RawPost]:
        days = 45 if q.geo == "world" else 120
        cutoff = int((datetime.now(timezone.utc) - timedelta(days=days)).timestamp())
        params = {
            "query": query,
            "tags": "story",
            "hitsPerPage": 40,
            "numericFilters": f"points>5,created_at_i>{cutoff}",
        }
        with httpx.Client(timeout=15) as c:
            r = c.get(self.HN_URL, params=params)
            r.raise_for_status()
            hits = r.json().get("hits", [])
        # niente risultati recenti: allarga (query piu' corta, finestra piu' ampia)
        if not hits:
            cutoff2 = int((datetime.now(timezone.utc) - timedelta(days=365)).timestamp())
            params["query"] = " ".join(query.split()[:2]) or query
            params["numericFilters"] = f"points>10,created_at_i>{cutoff2}"
            with httpx.Client(timeout=15) as c:
                r = c.get(self.HN_URL, params=params)
                r.raise_for_status()
                hits = r.json().get("hits", [])

        rows: list[RawPost] = []
        for h in hits:
            title = (h.get("title") or "").strip()
            if not title:
                continue
            points = int(h.get("points") or 0)
            n_comments = int(h.get("num_comments") or 0)
            url = h.get("url") or f"https://news.ycombinator.com/item?id={h.get('objectID')}"
            posted_at = _parse_dt(h.get("created_at"))
            body = _clean_html(h.get("story_text") or "")
            text = f"{title}\n\n{body}".strip() if body else title
            est_views = (points + 4 * n_comments) * 30 or 1
            rows.append(
                RawPost(
                    author_name=h.get("author") or "utente Hacker News",
                    author_headline="Hacker News",
                    author_profile_url=f"https://news.ycombinator.com/user?id={h.get('author')}",
                    niche=q.niche,
                    url=url,
                    text=text[:1200],
                    reactions=points,
                    comments=n_comments,
                    reposts=0,
                    views=est_views,
                    posted_at=posted_at,
                    data_source="hackernews",
                    score=engagement_score(
                        views=est_views, reactions=points, comments=n_comments,
                        reposts=0, posted_at=posted_at, half_life_days=30,
                    ),
                )
            )
        return rows

    def _reddit(self, query: str, q: DiscoveryQuery) -> list[RawPost]:
        window = self._WINDOW.get(q.geo, "past-week").replace("past-", "")
        subs = "+".join(self._SUBREDDITS)
        params = {
            "q": query, "restrict_sr": 0, "sort": "top",
            "t": window, "limit": 40, "type": "link",
        }
        headers = {"User-Agent": "AgenteLP-LUKA/0.1 (discovery; contact via github)"}
        url = f"https://www.reddit.com/r/{subs}/search.json"
        with httpx.Client(timeout=15, headers=headers, follow_redirects=True) as c:
            r = c.get(url, params=params)
            r.raise_for_status()
            children = r.json().get("data", {}).get("children", [])

        rows: list[RawPost] = []
        for ch in children:
            d = ch.get("data", {})
            title = (d.get("title") or "").strip()
            if not title:
                continue
            ups = int(d.get("ups") or d.get("score") or 0)
            n_comments = int(d.get("num_comments") or 0)
            body = _clean_html(d.get("selftext") or "")
            text = f"{title}\n\n{body}".strip() if body else title
            posted_at = (
                datetime.fromtimestamp(d["created_utc"], tz=timezone.utc)
                if d.get("created_utc") else None
            )
            est_views = (ups + 4 * n_comments) * 25 or 1
            rows.append(
                RawPost(
                    author_name=f"u/{d.get('author', 'utente')}",
                    author_headline=f"Reddit · r/{d.get('subreddit', '')}",
                    author_profile_url=f"https://www.reddit.com/user/{d.get('author', '')}",
                    niche=q.niche,
                    url="https://www.reddit.com" + d.get("permalink", ""),
                    text=text[:1200],
                    reactions=ups,
                    comments=n_comments,
                    reposts=0,
                    views=est_views,
                    posted_at=posted_at,
                    data_source="reddit",
                    score=engagement_score(
                        views=est_views, reactions=ups, comments=n_comments,
                        reposts=0, posted_at=posted_at, half_life_days=30,
                    ),
                )
            )
        return rows


def get_provider() -> DiscoveryProvider:
    s = get_settings()
    if s.has_apify:
        return ApifyDiscoveryProvider(s.apify_token, s.apify_actor)  # type: ignore[arg-type]
    if s.discovery_provider == "sample":
        return SampleDiscoveryProvider()
    return FreeDiscoveryProvider()
