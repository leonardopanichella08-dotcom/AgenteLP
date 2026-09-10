"""End-to-end sui percorsi principali dell'API (demo mode, provider sample)."""

from __future__ import annotations


def test_health_and_meta(client):
    assert client.get("/api/health").json() == {"status": "ok"}
    meta = client.get("/api/meta").json()
    assert meta["generation_mode"] == "demo"
    assert meta["discovery_provider"] == "sample"
    assert meta["linkedin_oauth"] is False
    assert {o["value"] for o in meta["geo_options"]} == {"world", "europe", "italy"}


def test_seed_connections_have_brand_profile(client):
    conns = client.get("/api/connections").json()
    assert len(conns) >= 2
    for c in conns:
        assert c["brand_profile"] is not None
        assert c["brand_profile"]["mission"]


def test_create_connection_runs_onboarding(client):
    r = client.post(
        "/api/connections",
        json={
            "account_type": "company",
            "display_name": "Test Co",
            "headline": "Osservabilità per team platform",
            "industry": "DevTools",
            "raw_about": "Aiutiamo i team platform a ridurre il MTTR con tracce distribuite.",
        },
    )
    assert r.status_code == 201
    body = r.json()
    assert body["brand_profile"]["mission"]
    assert body["brand_profile"]["generated_by_model"] in {"heuristic", "seed"}


def test_upload_document_indexes_chunks(client, personal_connection):
    cid = personal_connection["id"]
    files = {
        "file": (
            "nota.txt",
            "Case study: scale-up SaaS a Milano, ciclo di vendita da 90 a 62 giorni "
            "dopo aver introdotto la qualificazione predittiva degli account.".encode(),
            "text/plain",
        )
    }
    r = client.post(f"/api/connections/{cid}/documents", files=files)
    assert r.status_code == 201
    assert r.json()["status"] == "indexed"

    docs = client.get(f"/api/connections/{cid}/documents").json()
    assert any(d["filename"] == "nota.txt" for d in docs)


def test_discovery_full_cycle(client, personal_connection):
    cid = personal_connection["id"]
    r = client.post(
        "/api/tasks/discovery",
        json={
            "connection_id": cid,
            "niche": "AI B2B / Sales Intelligence",
            "keywords_primary": ["sales", "automation", "icp"],
            "keywords_secondary": ["revops", "pipeline"],
            "geo": "europe",
            "limit": 5,
            "variants_per_post": 2,
        },
    )
    assert r.status_code == 201
    task = r.json()
    assert task["status"] == "succeeded"
    assert 1 <= len(task["posts"]) <= 5

    ranks = [p["rank"] for p in task["posts"]]
    assert ranks == sorted(ranks)
    scores = [p["engagement_score"] for p in task["posts"]]
    assert scores == sorted(scores, reverse=True)

    first = task["posts"][0]
    kinds = {r_["kind"] for r_ in first["responses"]}
    assert "comment" in kinds and "repost_with_comment" in kinds
    assert all(r_["deeplink_url"] for r_ in first["responses"])
    assert all(len(r_["body"]) > 80 for r_ in first["responses"])


def test_regenerate_replaces_not_appends(client, personal_connection):
    cid = personal_connection["id"]
    task = client.post(
        "/api/tasks/discovery",
        json={"connection_id": cid, "niche": "AI B2B", "keywords_primary": ["sales"],
              "geo": "italy", "limit": 2, "variants_per_post": 2},
    ).json()
    post_id = task["posts"][0]["id"]

    def counts(t):
        p = next(p for p in t["posts"] if p["id"] == post_id)
        c = sum(1 for r in p["responses"] if r["kind"] == "comment")
        rp = sum(1 for r in p["responses"] if r["kind"] == "repost_with_comment")
        return c, rp

    before = counts(task)
    after = counts(client.post(f"/api/tasks/posts/{post_id}/regenerate", json={"kind": "comment"}).json())
    assert before == after == (2, 1)


def test_task_listing(client):
    tasks = client.get("/api/tasks").json()
    assert isinstance(tasks, list) and tasks
    assert all(t["agent_key"] == "luka" for t in tasks)
