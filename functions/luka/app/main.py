from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import get_settings
from .db import init_db
from .routers import auth, connections, knowledge, tasks
from .seed import seed_demo


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


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/api/meta")
def meta():
    s = get_settings()
    return {
        "generation_mode": "llm" if s.has_llm else "demo",
        "model": s.anthropic_model if s.has_llm else None,
        "discovery_provider": s.discovery_label,
        "linkedin_oauth": s.has_linkedin_oauth,
        "geo_options": [
            {"value": "world", "label": "Mondo"},
            {"value": "europe", "label": "Europa"},
            {"value": "italy", "label": "Italia"},
        ],
    }


@app.get("/")
def root():
    return {"service": "luka", "docs": "/docs", "health": "/api/health"}
