"""Accesso al motore solo dal portale METODOS, senza segreti da copiare.

Il portale firma un codice a scadenza (con un segreto che resta *solo* nel portale). Il browser lo manda qui;
il motore non lo capisce: chiede al portale `GET {METODOS_URL}/api/reels/verify?t=…` e lavora solo se risponde ok.
Se METODOS_URL non è impostato (sviluppo locale, demo) l'accesso è libero.
"""
from __future__ import annotations

import os
import time

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

PROTECTED = ("/api/projects", "/api/demo")
http = httpx.Client(timeout=8)
_ok: dict[str, float] = {}          # token valido -> scadenza (epoch)
_bad: dict[str, float] = {}         # token rifiutato -> fino a quando non richiedere (anti-martellamento)


def portal_url() -> str:
    return os.environ.get("METODOS_URL", "").rstrip("/")


def verify(token: str) -> bool:
    now = time.time()
    if _ok.get(token, 0) > now:
        return True
    if _bad.get(token, 0) > now:
        return False
    try:
        r = http.get(f"{portal_url()}/api/reels/verify", params={"t": token})
        j = r.json() if r.status_code == 200 else {}
    except Exception:
        return False                       # portale irraggiungibile: mai aprire per errore
    if j.get("ok"):
        _ok[token] = min(float(j.get("exp", now + 60)), now + 600)   # ricontrolla al massimo ogni 10 min
        return True
    _bad[token] = now + 5
    return False


def install(app: FastAPI) -> None:
    @app.middleware("http")
    async def guard(request: Request, call_next):
        if portal_url() and request.method != "OPTIONS" and request.url.path.startswith(PROTECTED):
            h = request.headers.get("authorization", "")
            token = h[7:] if h.lower().startswith("bearer ") else request.query_params.get("t", "")
            if not token or not verify(token):
                return JSONResponse({"detail": "Accesso non autorizzato: riapri la scheda Reels dal portale."}, status_code=401)
        return await call_next(request)
