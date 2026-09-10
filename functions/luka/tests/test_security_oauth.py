"""Cifratura token + macchina a stati OAuth LinkedIn (offline)."""

from __future__ import annotations

import time

from app.crypto import decrypt, encrypt
from app.linkedin_oauth import build_authorize_url, make_state, read_state


def test_token_encryption_round_trip():
    secret = "AQX-linkedin-access-token-123"
    blob = encrypt(secret)
    assert blob != secret
    assert decrypt(blob) == secret
    assert decrypt("non-un-token-valido") is None


def test_oauth_state_round_trip_and_type():
    for account_type in ("personal", "company"):
        s = make_state(account_type)
        assert read_state(s) == account_type


def test_oauth_state_rejects_tamper_and_expiry():
    s = make_state("personal")
    assert read_state(s[:-4] + "AAAA") is None  # manomesso
    assert read_state("") is None

    old = make_state("personal")
    # simula scadenza spostando indietro il tempo di lettura
    import app.linkedin_oauth as mod

    mod.STATE_TTL_SECONDS = -1
    try:
        assert read_state(old) is None
    finally:
        mod.STATE_TTL_SECONDS = 600


def test_authorize_url_contains_required_params(monkeypatch):
    from app.config import get_settings

    get_settings.cache_clear()
    monkeypatch.setenv("LINKEDIN_CLIENT_ID", "test-client")
    monkeypatch.setenv("LINKEDIN_CLIENT_SECRET", "test-secret")
    try:
        url = build_authorize_url("personal")
        assert url.startswith("https://www.linkedin.com/oauth/v2/authorization?")
        assert "client_id=test-client" in url
        assert "response_type=code" in url
        assert "scope=openid" in url
        assert "state=" in url
    finally:
        get_settings.cache_clear()


def test_auth_status_endpoint(client):
    body = client.get("/api/auth/linkedin/status").json()
    assert body["configured"] is False
    assert "openid" in body["scopes"]


def test_start_without_config_returns_400(client):
    r = client.get("/api/auth/linkedin/start", follow_redirects=False)
    assert r.status_code == 400
