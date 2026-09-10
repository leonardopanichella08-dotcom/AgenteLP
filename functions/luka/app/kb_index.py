from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from .agent.retriever import LexicalRetriever
from .models import KbChunk


def connection_chunks(
    db: Session, connection_id: str, query: str | None = None, k: int = 6
) -> list[str]:
    rows = db.scalars(
        select(KbChunk)
        .where(KbChunk.connection_id == connection_id)
        .order_by(KbChunk.chunk_index)
    ).all()
    contents = [r.content for r in rows]
    if not contents:
        return []
    if not query:
        return contents[:k]
    return LexicalRetriever(contents).search(query, k=k)
