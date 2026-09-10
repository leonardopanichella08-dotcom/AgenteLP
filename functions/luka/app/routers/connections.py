from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..agent.onboarding import synthesize_brand_profile
from ..agent.profile_scraper import extract_username, scrape_profile, to_raw_about
from ..config import get_settings
from ..db import get_db
from ..deps import get_or_create_user
from ..kb_index import connection_chunks
from ..models import BrandProfile, LinkedInConnection
from ..schemas import ConnectionCreate, ConnectionFromUsernameIn, ConnectionOut

router = APIRouter(prefix="/api/connections", tags=["connections"])


def _to_out(conn: LinkedInConnection) -> ConnectionOut:
    out = ConnectionOut.model_validate(conn)
    out.documents_count = len(conn.documents)
    return out


def run_onboarding_public(db: Session, conn: LinkedInConnection) -> BrandProfile:
    return _run_onboarding(db, conn)


def _maybe_enrich_from_linkedin(conn: LinkedInConnection) -> list[str]:
    """Se c'e' uno username LinkedIn e Apify e' configurato, arricchisce la
    connessione con i dati del profilo. Ritorna gli hashtag del creator."""
    if not get_settings().apify_token:
        return []
    handle = conn.vanity_url or ""
    if not handle:
        return []
    prof = scrape_profile(handle)
    if not prof:
        return []
    conn.display_name = conn.display_name or prof["display_name"]
    conn.headline = conn.headline or prof.get("headline") or None
    conn.industry = conn.industry or prof.get("industry_hint") or None
    conn.avatar_url = conn.avatar_url or prof.get("avatar_url")
    conn.linkedin_urn = conn.linkedin_urn or f"urn:li:person:{prof['username']}"
    scraped = to_raw_about(prof)
    if scraped and (not conn.raw_about or len(conn.raw_about) < len(scraped)):
        conn.raw_about = scraped
    return prof.get("hashtags") or []


def _run_onboarding(db: Session, conn: LinkedInConnection) -> BrandProfile:
    hashtags: list[str] = []
    try:
        hashtags = _maybe_enrich_from_linkedin(conn)
        db.add(conn)
        db.flush()
    except Exception:  # noqa: BLE001
        db.rollback()

    snippets = connection_chunks(db, conn.id, query=conn.headline or conn.display_name, k=6)
    data = synthesize_brand_profile(
        display_name=conn.display_name,
        account_type=conn.account_type,
        headline=conn.headline,
        industry=conn.industry,
        raw_about=conn.raw_about,
        kb_snippets=snippets,
        hashtags=hashtags,
    )
    bp = conn.brand_profile or BrandProfile(connection_id=conn.id)
    bp.mission = data.get("mission", "")
    bp.value_proposition = data.get("value_proposition", "")
    bp.icp = data.get("icp", "")
    bp.market_context = data.get("market_context", "")
    bp.tone_of_voice = data.get("tone_of_voice", bp.tone_of_voice)
    bp.niche = data.get("niche", "") or bp.niche
    bp.keywords_primary = data.get("keywords_primary", []) or bp.keywords_primary
    bp.keywords_secondary = data.get("keywords_secondary", []) or bp.keywords_secondary
    bp.generated_by_model = data.get("generated_by_model")
    db.add(bp)
    db.commit()
    db.refresh(conn)
    return bp


@router.get("", response_model=list[ConnectionOut])
def list_connections(db: Session = Depends(get_db)):
    user = get_or_create_user(db)
    rows = db.scalars(
        select(LinkedInConnection)
        .where(LinkedInConnection.user_id == user.id)
        .order_by(LinkedInConnection.created_at.desc())
    ).all()
    return [_to_out(c) for c in rows]


@router.post("", response_model=ConnectionOut, status_code=201)
def create_connection(payload: ConnectionCreate, db: Session = Depends(get_db)):
    user = get_or_create_user(db)
    conn = LinkedInConnection(
        user_id=user.id,
        account_type=payload.account_type,
        display_name=payload.display_name,
        headline=payload.headline,
        industry=payload.industry,
        vanity_url=payload.vanity_url,
        raw_about=payload.raw_about,
        scopes=[],
    )
    db.add(conn)
    db.commit()
    db.refresh(conn)
    _run_onboarding(db, conn)
    return _to_out(conn)


@router.post("/from-username", response_model=ConnectionOut, status_code=201)
def create_from_username(payload: ConnectionFromUsernameIn, db: Session = Depends(get_db)):
    """Collega un profilo dal solo username: scrape del profilo LinkedIn +
    analisi automatica (nicchia e keyword incluse)."""
    s = get_settings()
    if not s.apify_token:
        raise HTTPException(
            400,
            "Scraping profilo non disponibile: manca APIFY_TOKEN. Usa l'inserimento manuale.",
        )
    handle = extract_username(payload.username)
    if not handle:
        raise HTTPException(422, "Username non valido")

    prof = scrape_profile(handle)
    if not prof:
        raise HTTPException(
            502,
            "Profilo LinkedIn non trovato o non pubblico. Controlla lo username o inserisci i dati a mano.",
        )

    user = get_or_create_user(db)
    conn = db.scalar(
        select(LinkedInConnection).where(
            LinkedInConnection.user_id == user.id,
            LinkedInConnection.vanity_url == prof["profile_url"],
        )
    )
    if conn is None:
        conn = LinkedInConnection(user_id=user.id, account_type=payload.account_type, scopes=[])
        db.add(conn)
    conn.account_type = payload.account_type
    conn.display_name = prof["display_name"]
    conn.headline = prof.get("headline") or None
    conn.industry = prof.get("industry_hint") or None
    conn.vanity_url = prof["profile_url"]
    conn.avatar_url = prof.get("avatar_url")
    conn.linkedin_urn = f"urn:li:person:{prof['username']}"
    conn.raw_about = to_raw_about(prof)
    conn.auth_method = "scrape"
    db.commit()
    db.refresh(conn)

    _run_onboarding(db, conn)
    return _to_out(conn)


@router.get("/{connection_id}", response_model=ConnectionOut)
def get_connection(connection_id: str, db: Session = Depends(get_db)):
    conn = db.get(LinkedInConnection, connection_id)
    if conn is None:
        raise HTTPException(404, "Connessione non trovata")
    return _to_out(conn)


@router.post("/{connection_id}/reanalyze", response_model=ConnectionOut)
def reanalyze(connection_id: str, db: Session = Depends(get_db)):
    conn = db.get(LinkedInConnection, connection_id)
    if conn is None:
        raise HTTPException(404, "Connessione non trovata")
    _run_onboarding(db, conn)
    return _to_out(conn)


@router.delete("/{connection_id}", status_code=204)
def delete_connection(connection_id: str, db: Session = Depends(get_db)):
    conn = db.get(LinkedInConnection, connection_id)
    if conn is not None:
        db.delete(conn)
        db.commit()
