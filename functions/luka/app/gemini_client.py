"""Client minimale per l'API Gemini (generativelanguage v1beta).

Solo httpx: nessun SDK. Retry su 429/5xx perché i modelli `*-latest`
vanno spesso in 503 "high demand".
"""

from __future__ import annotations

import time
from typing import Any

import httpx

_BASE = "https://generativelanguage.googleapis.com/v1beta/models"
_RETRY_STATUS = {429, 500, 502, 503, 504}
_FALLBACK_MODELS = ["gemini-flash-latest", "gemini-3.5-flash", "gemini-flash-lite-latest"]


def generate_content(
    *,
    api_key: str,
    model: str,
    body: dict[str, Any],
    timeout: float = 60.0,
    max_attempts: int = 3,
) -> dict[str, Any]:
    """Ritorna il JSON della risposta. Solleva httpx.HTTPStatusError se, dopo
    i retry e i modelli di fallback, non arriva un 2xx."""
    models = [model, *[m for m in _FALLBACK_MODELS if m != model]]
    last_exc: Exception | None = None

    for m in models:
        url = f"{_BASE}/{m}:generateContent"
        for attempt in range(max_attempts):
            try:
                with httpx.Client(timeout=timeout) as c:
                    r = c.post(url, params={"key": api_key}, json=body)
                if r.status_code in _RETRY_STATUS:
                    last_exc = httpx.HTTPStatusError(
                        f"{r.status_code} {r.reason_phrase}", request=r.request, response=r
                    )
                    time.sleep(1.5 * (attempt + 1))
                    continue
                r.raise_for_status()
                return r.json()
            except httpx.HTTPStatusError as exc:
                last_exc = exc
                if exc.response is not None and exc.response.status_code not in _RETRY_STATUS:
                    break  # errore non transitorio: prova il modello successivo
                time.sleep(1.5 * (attempt + 1))
            except httpx.HTTPError as exc:
                last_exc = exc
                time.sleep(1.0 * (attempt + 1))

    assert last_exc is not None
    raise last_exc


def extract_text(data: dict[str, Any]) -> str:
    parts = data.get("candidates", [{}])[0].get("content", {}).get("parts", [])
    return "".join(p.get("text", "") for p in parts)


def usage(data: dict[str, Any]) -> tuple[int | None, int | None]:
    u = data.get("usageMetadata", {})
    return u.get("promptTokenCount"), u.get("candidatesTokenCount")
