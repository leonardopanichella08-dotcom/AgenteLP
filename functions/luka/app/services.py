from __future__ import annotations

import io


def extract_text(filename: str, data: bytes, mime_type: str) -> str:
    name = filename.lower()
    if name.endswith(".pdf") or mime_type == "application/pdf":
        return _pdf(data)
    if name.endswith(".docx") or "wordprocessingml" in mime_type:
        return _docx(data)
    # txt / md / csv / fallback
    try:
        return data.decode("utf-8", errors="ignore")
    except Exception:
        return ""


def _pdf(data: bytes) -> str:
    try:
        from pypdf import PdfReader
    except ImportError:  # pragma: no cover
        return ""
    reader = PdfReader(io.BytesIO(data))
    return "\n\n".join((page.extract_text() or "") for page in reader.pages).strip()


def _docx(data: bytes) -> str:
    try:
        import docx
    except ImportError:  # pragma: no cover
        return ""
    document = docx.Document(io.BytesIO(data))
    return "\n".join(p.text for p in document.paragraphs).strip()
