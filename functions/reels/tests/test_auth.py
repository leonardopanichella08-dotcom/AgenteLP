import time

import httpx
import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def guarded(tmp_path, monkeypatch):
    import app.store as store
    import app.auth as auth
    monkeypatch.setattr(store, "DATA_DIR", tmp_path)
    monkeypatch.setenv("METODOS_URL", "https://portale.example")
    calls = []

    def handler(req: httpx.Request):
        calls.append(str(req.url))
        assert req.url.host == "portale.example" and req.url.path == "/api/reels/verify"
        if req.url.params["t"] == "buono":
            return httpx.Response(200, json={"ok": True, "exp": time.time() + 3600})
        return httpx.Response(401, json={"detail": "no"})
    monkeypatch.setattr(auth, "http", httpx.Client(transport=httpx.MockTransport(handler)))
    auth._ok.clear(); auth._bad.clear()
    import importlib, app.main as m
    importlib.reload(m)                      # la CORS si legge all'avvio: ricarica con METODOS_URL impostato
    return TestClient(m.app), calls


def test_requests_without_valid_code_are_refused(guarded):
    c, calls = guarded
    assert c.get("/api/projects").status_code == 401
    assert c.get("/api/projects", headers={"Authorization": "Bearer sbagliato"}).status_code == 401
    assert c.post("/api/demo", json={}).status_code == 401           # niente CPU gratis per sconosciuti
    assert c.get("/api/projects/abcdef0123/media/x?t=sbagliato").status_code == 401


def test_valid_code_header_or_query_and_cache(guarded):
    c, calls = guarded
    assert c.get("/api/projects", headers={"Authorization": "Bearer buono"}).status_code == 200
    assert c.get("/api/projects?t=buono").status_code == 200          # <video src> e download non possono mandare header
    assert len([u for u in calls if "t=buono" in u]) == 1             # il secondo giro usa la cache


def test_public_endpoints_and_preflight_stay_open_and_cors_is_portal_only(guarded):
    c, _ = guarded
    assert c.get("/api/health").status_code == 200 and c.get("/api/meta").status_code == 200
    r = c.options("/api/projects", headers={"Origin": "https://portale.example", "Access-Control-Request-Method": "POST",
                                            "Access-Control-Request-Headers": "authorization"})
    assert r.status_code == 200 and r.headers["access-control-allow-origin"] == "https://portale.example"
    r = c.get("/api/projects", headers={"Origin": "https://evil.example"})
    assert "access-control-allow-origin" not in r.headers


def test_portal_down_never_opens_the_door(guarded, monkeypatch):
    import app.auth as auth
    c, _ = guarded
    def boom(req): raise httpx.ConnectError("down")
    monkeypatch.setattr(auth, "http", httpx.Client(transport=httpx.MockTransport(boom)))
    assert c.get("/api/projects?t=buono").status_code == 401


@pytest.fixture(autouse=True)
def _restore_main():
    yield
    import importlib, os
    os.environ.pop("METODOS_URL", None)
    import app.main as m
    importlib.reload(m)
