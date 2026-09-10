from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import User

DEMO_EMAIL = "demo@luka.app"


def get_or_create_user(db: Session) -> User:
    """v1 single-tenant: un utente demo. Sostituibile con auth JWT reale."""
    user = db.scalar(select(User).where(User.email == DEMO_EMAIL))
    if user is None:
        user = User(email=DEMO_EMAIL, full_name="Utente Demo", locale="it")
        db.add(user)
        db.commit()
        db.refresh(user)
    return user


def build_deeplink(post_url: str) -> str:
    """LinkedIn non consente commenti pre-compilati via URL: il deep-link apre
    il post, l'utente incolla il testo copiato. Questo e' il flusso compliant."""
    return post_url
