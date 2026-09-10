from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest
from cryptography.fernet import Fernet

# Ambiente isolato PRIMA di importare l'app (get_settings e' cache-ato).
_TMP = tempfile.mkdtemp(prefix="luka-tests-")
os.environ["DATABASE_URL"] = f"sqlite:///{Path(_TMP) / 'test.db'}"
os.environ["APP_ENCRYPTION_KEY"] = Fernet.generate_key().decode()
# Isola i test da .env: niente rete, generazione deterministica.
os.environ["DISCOVERY_PROVIDER"] = "sample"
os.environ["LLM_PROVIDER"] = "demo"
for _k in ("ANTHROPIC_API_KEY", "GEMINI_API_KEY", "APIFY_TOKEN"):
    os.environ.pop(_k, None)


@pytest.fixture(scope="session")
def client():
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="session")
def personal_connection(client):
    conns = client.get("/api/connections").json()
    return next(c for c in conns if c["account_type"] == "personal")
