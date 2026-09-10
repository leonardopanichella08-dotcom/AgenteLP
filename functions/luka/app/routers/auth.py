from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..crypto import encrypt
from ..db import get_db
from ..deps import get_or_create_user
from ..linkedin_oauth import build_authorize_url, exchange_code, fetch_identity, read_state
from ..models import LinkedInConnection
from ..routers.connections import run_onboarding_public

log = logging.getLogger("luka.auth")
router = APIRouter(prefix="/api/auth/linkedin", tags=["auth"])


@router.get("/status")
def status():
    s = get_settings()
    return {
        "configured": s.has_linkedin_oauth,
        "scopes": s.scope_list,
        "redirect_uri": s.linkedin_redirect_uri,
    }


@router.get("/start")
def start(account_type: str = Query("personal", pattern="^(personal|company)$")):
    s = get_settings()
    if not s.has_linkedin_oauth:
        raise HTTPException(
            400,
            "OAuth LinkedIn non configurato: imposta LINKEDIN_CLIENT_ID e "
            "LINKEDIN_CLIENT_SECRET nel file .env.",
        )
    return RedirectResponse(build_authorize_url(account_type), status_code=307)


@router.get("/callback")
async def callback(
    db: Session = Depends(get_db),
    code: str | None = Query(None),
    state: str | None = Query(None),
    error: str | None = Query(None),
    error_description: str | None = Query(None),
):
    s = get_settings()
    frontend = s.frontend_url.rstrip("/")

    if error:
        return RedirectResponse(f"{frontend}/?linkedin=error&reason={error}")

    account_type = read_state(state or "")
    if not code or account_type is None:
        return RedirectResponse(f"{frontend}/?linkedin=error&reason=bad_state")

    try:
        token = await exchange_code(code)
        identity = await fetch_identity(token)
    except Exception as exc:  # noqa: BLE001
        log.exception("LinkedIn OAuth callback fallita")
        return RedirectResponse(f"{frontend}/?linkedin=error&reason=exchange_failed")

    user = get_or_create_user(db)
    urn = f"urn:li:person:{identity.sub}" if identity.sub else f"urn:li:person:{identity.name}"

    conn = db.scalar(
        select(LinkedInConnection).where(
            LinkedInConnection.user_id == user.id,
            LinkedInConnection.linkedin_urn == urn,
        )
    )
    if conn is None:
        conn = LinkedInConnection(user_id=user.id, account_type=account_type, linkedin_urn=urn)
        db.add(conn)

    conn.account_type = account_type
    conn.display_name = identity.name
    conn.avatar_url = identity.picture
    conn.auth_method = "oauth"
    conn.access_token_enc = encrypt(token)
    conn.scopes = s.scope_list
    conn.status = "active"
    db.commit()
    db.refresh(conn)

    # Onboarding: sintesi brand profile (euristica o Claude)
    try:
        run_onboarding_public(db, conn)
    except Exception:  # noqa: BLE001
        log.warning("Onboarding post-OAuth non riuscito, si prosegue comunque.")

    return RedirectResponse(f"{frontend}/?linkedin=connected&id={conn.id}")
