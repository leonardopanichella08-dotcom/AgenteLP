from __future__ import annotations

import logging
from collections.abc import Iterator

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .config import get_settings

log = logging.getLogger("luka.db")

# Micro-migrazioni: colonne aggiunte dopo il primo deploy.
# create_all() non tocca tabelle esistenti, quindi le aggiungiamo a mano.
_ADD_COLUMNS: dict[str, dict[str, str]] = {
    "brand_profiles": {
        "niche": "TEXT DEFAULT ''",
        "keywords_primary": "JSON",
        "keywords_secondary": "JSON",
    },
    "linkedin_connections": {
        "avatar_url": "VARCHAR(600)",
        "linkedin_urn": "VARCHAR(255)",
        "auth_method": "VARCHAR(16) DEFAULT 'manual'",
    },
}


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


def _ensure_columns() -> None:
    insp = inspect(engine)
    existing_tables = set(insp.get_table_names())
    is_sqlite = engine.url.get_backend_name() == "sqlite"
    with engine.begin() as conn:
        for table, cols in _ADD_COLUMNS.items():
            if table not in existing_tables:
                continue
            have = {c["name"] for c in insp.get_columns(table)}
            for name, ddl in cols.items():
                if name in have:
                    continue
                coltype = "TEXT" if (is_sqlite and ddl == "JSON") else ddl
                try:
                    conn.execute(text(f'ALTER TABLE {table} ADD COLUMN {name} {coltype}'))
                    log.info("aggiunta colonna %s.%s", table, name)
                except Exception as exc:  # noqa: BLE001
                    log.warning("ALTER TABLE %s ADD %s fallita: %s", table, name, exc)


def init_db() -> None:
    from . import models  # noqa: F401  — register mappers

    Base.metadata.create_all(bind=engine)
    _ensure_columns()
