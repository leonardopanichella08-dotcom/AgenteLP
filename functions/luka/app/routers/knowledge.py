from __future__ import annotations

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..agent.retriever import chunk_text
from ..db import get_db
from ..models import KbChunk, KbDocument, LinkedInConnection
from ..schemas import KbDocumentOut
from ..services import extract_text

router = APIRouter(prefix="/api/connections/{connection_id}/documents", tags=["knowledge"])

MAX_BYTES = 8 * 1024 * 1024  # 8 MB


@router.get("", response_model=list[KbDocumentOut])
def list_documents(connection_id: str, db: Session = Depends(get_db)):
    rows = db.scalars(
        select(KbDocument)
        .where(KbDocument.connection_id == connection_id)
        .order_by(KbDocument.created_at.desc())
    ).all()
    return rows


@router.post("", response_model=KbDocumentOut, status_code=201)
async def upload_document(
    connection_id: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    conn = db.get(LinkedInConnection, connection_id)
    if conn is None:
        raise HTTPException(404, "Connessione non trovata")

    data = await file.read()
    if len(data) > MAX_BYTES:
        raise HTTPException(413, "File troppo grande (max 8 MB)")

    doc = KbDocument(
        connection_id=connection_id,
        filename=file.filename or "documento",
        mime_type=file.content_type or "application/octet-stream",
        size_bytes=len(data),
        status="processing",
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)

    try:
        text = extract_text(doc.filename, data, doc.mime_type)
        chunks = chunk_text(text)
        for i, c in enumerate(chunks):
            db.add(
                KbChunk(
                    document_id=doc.id,
                    connection_id=connection_id,
                    chunk_index=i,
                    content=c,
                    embedding=None,
                )
            )
        doc.status = "indexed" if chunks else "failed"
        doc.error = None if chunks else "Nessun testo estraibile dal file"
    except Exception as exc:  # noqa: BLE001
        doc.status = "failed"
        doc.error = str(exc)
    db.add(doc)
    db.commit()
    db.refresh(doc)
    return doc


@router.delete("/{document_id}", status_code=204)
def delete_document(connection_id: str, document_id: str, db: Session = Depends(get_db)):
    doc = db.get(KbDocument, document_id)
    if doc is not None:
        db.delete(doc)
        db.commit()
