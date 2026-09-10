from __future__ import annotations

from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .config import get_settings


def _normalize_url(url: str) -> str:
    """Neon/Heroku give `postgres://`; SQLAlchemy 2 wants an explicit driver."""
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql+psycopg://", 1)
    if url.startswith("postgresql://") and "+psycopg" not in url:
        return url.replace("postgresql://", "postgresql+psycopg://", 1)
    return url


_settings = get_settings()
_url = _normalize_url(_settings.database_url)
_connect_args = {"check_same_thread": False} if _url.startswith("sqlite") else {}

engine = create_engine(_url, connect_args=_connect_args, pool_pre_ping=True, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


class Base(DeclarativeBase):
    pass


def get_db() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    from . import models  # noqa: F401  — register mappers

    Base.metadata.create_all(bind=engine)
