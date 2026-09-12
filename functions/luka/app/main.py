from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from .config import get_settings
from .db import init_db
from .routers import andrea, auth, connections, knowledge, tasks
from .seed import seed_demo

_WEB_DIST = Path(__file__).resolve().parent.parent / "web" / "dist"


@asynccontextmanager
async def lifespan(app: FastAPI):
    _bootstrap()
    yield


def _bootstrap() -> None:
    """Idempotente: sicuro sia all'import (serverless) sia nel lifespan."""
    init_db()
    seed_demo()


settings = get_settings()

# Esegui anche all'import: su alcune piattaforme serverless il lifespan
# non viene eseguito a ogni invocazione.
_bootstrap()

app = FastAPI(
    title="LUKA API",
    version="0.1.0",
    description="Agente LinkedIn: onboarding, discovery post virali, engagement generativo.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_list or ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(connections.router)
app.include_router(knowledge.router)
app.include_router(tasks.router)
app.include_router(andrea.router)


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/api/meta")
def meta():
    s = get_settings()
    return {
        "generation_mode": "llm" if s.has_llm else "demo",
        "llm_provider": s.active_llm,
        "model": s.active_model,
        "discovery_provider": s.discovery_label,
        "linkedin_oauth": s.has_linkedin_oauth,
        "geo_options": [
            {"value": "world", "label": "Mondo"},
            {"value": "europe", "label": "Europa"},
            {"value": "italy", "label": "Italia"},
        ],
    }


@app.get("/api")
def api_root():
    return {"service": "luka", "docs": "/docs", "health": "/api/health"}


# ── Frontend statico (build Vite) servito dallo stesso processo ──────────
# In locale senza build la cartella non esiste: l'API funziona lo stesso.
if _WEB_DIST.is_dir():
    _INDEX = _WEB_DIST / "index.html"
    # index.html cambia ad ogni deploy (nuovi hash negli <script src>) quindi
    # non va MAI cacheato: altrimenti un browser con l'HTML vecchio richiede
    # bundle .js/.css gia' cancellati dal deploy successivo, e senza questo
    # header il fallback qui sotto li servirebbe con index.html (text/html)
    # invece di un 404 -> "Failed to load module script" -> pagina bianca.
    _NO_CACHE = {"Cache-Control": "no-cache, no-store, must-revalidate"}
    # gli asset in /assets/ hanno hash nel nome (immutabili): cache lunga ok.
    _IMMUTABLE_CACHE = {"Cache-Control": "public, max-age=31536000, immutable"}

    @app.get("/", include_in_schema=False)
    def _spa_root():
        return FileResponse(_INDEX, headers=_NO_CACHE)

    @app.get("/{full_path:path}", include_in_schema=False)
    def _spa_fallback(full_path: str):
        candidate = (_WEB_DIST / full_path).resolve()
        if _WEB_DIST in candidate.parents and candidate.is_file():
            headers = _IMMUTABLE_CACHE if full_path.startswith("assets/") else None
            return FileResponse(candidate, headers=headers)
        # Un path con estensione (.js/.css/.map/...) che non esiste e' un
        # asset di una build vecchia, non una rotta client-side: 404 vero,
        # mai l'index.html (altrimenti il browser lo esegue come modulo JS
        # e fallisce per mismatch di MIME type restando su schermo bianco).
        if Path(full_path).suffix:
            raise HTTPException(status_code=404)
        return FileResponse(_INDEX, headers=_NO_CACHE)  # SPA: rotta client -> index.html
else:
    @app.get("/")
    def root():
        return {"service": "luka", "note": "frontend non buildato", "health": "/api/health"}
