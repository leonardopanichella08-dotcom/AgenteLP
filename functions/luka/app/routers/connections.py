from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..agent.onboarding import synthesize_brand_profile
from ..db import get_db
from ..deps import get_or_create_user
from ..kb_index import connection_chunks
from ..models import BrandProfile, LinkedInConnection
from ..schemas import ConnectionCreate, ConnectionOut

router = APIRouter(prefix="/api/connections", tags=["connections"])


def _to_out(conn: LinkedInConnection) -> ConnectionOut:
    out = ConnectionOut.model_validate(conn)
    out.documents_count = len(conn.documents)
    return out


def run_onboarding_public(db: Session, conn: LinkedInConnection) -> BrandProfile:
    """Alias pubblico, usato anche dal callback OAuth."""
    return _run_onboarding(db, conn)


def _run_onboarding(db: Session, conn: LinkedInConnection) -> BrandProfile:
    snippets = connection_chunks(db, conn.id, query=conn.headline or conn.display_name, k=6)
    data = synthesize_brand_profile(
        display_name=conn.display_name,
        account_type=conn.account_type,
        headline=conn.headline,
        industry=conn.industry,
        raw_about=conn.raw_about,
        kb_snippets=snippets,
    )
    bp = conn.brand_profile or BrandProfile(connection_id=conn.id)
    bp.mission = data.get("mission", "")
    bp.value_proposition = data.get("value_proposition", "")
    bp.icp = data.get("icp", "")
    bp.market_context = data.get("market_context", "")
    bp.tone_of_voice = data.get("tone_of_voice", bp.tone_of_voice)
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
