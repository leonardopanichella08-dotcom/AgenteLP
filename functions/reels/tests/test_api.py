import json
import time

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client(tmp_path, monkeypatch):
    import app.store as store
    monkeypatch.setattr(store, "DATA_DIR", tmp_path)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("DEEPGRAM_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    from app.main import app
    return TestClient(app)


def wait(client, pid, until=("ready", "error", "done"), timeout=180):
    t0 = time.time()
    while time.time() - t0 < timeout:
        st = client.get(f"/api/projects/{pid}").json()
        if st["status"] in until:
            return st
        time.sleep(0.4)
    raise TimeoutError(st)


def test_meta_formats_schema_prompt(client):
    assert client.get("/api/meta").json()["function"] == "reels"
    assert {f["id"] for f in client.get("/api/formats").json()} == {"9:16", "4:5", "1:1", "16:9"}
    assert "reels" in client.get("/api/schema").json()["properties"]
    assert "MODALITÀ B" in client.get("/api/system-prompt").json()["markdown"]


def test_validation_errors(client):
    r = client.post("/api/projects", data={"mode": "x"}, files=[("files", ("a.mp4", b"x", "video/mp4"))])
    assert r.status_code == 422
    r = client.post("/api/projects", data={"mode": "script_assembly"}, files=[("files", ("a.mp4", b"x", "video/mp4"))])
    assert r.status_code == 422 and "script" in r.json()["detail"]
    r = client.post("/api/projects", data={"mode": "long_form_extraction", "formats": "3:2"}, files=[("files", ("a.mp4", b"x", "video/mp4"))])
    assert r.status_code == 422
    assert client.get("/api/projects/abcdef0123").status_code == 404
    assert client.get("/api/projects/..%2Fetc").status_code in (404, 422)


def test_upload_without_asr_gives_actionable_error(client, podcast):
    with open(podcast["path"], "rb") as f:
        r = client.post("/api/projects", data={"mode": "long_form_extraction"}, files=[("files", ("podcast.mp4", f, "video/mp4"))])
    st = wait(client, r.json()["id"])
    assert st["status"] == "error" and st["error_kind"] == "asr_unavailable"
    assert "huggingface.co" in st["error"] and "GROQ_API_KEY" in st["error"]   # pesi Whisper non scaricabili: messaggio azionabile


def test_upload_with_sidecar_transcript_full_flow(client, podcast, tmp_path):
    tr = json.dumps(podcast["transcript"].to_dict()).encode()
    with open(podcast["path"], "rb") as f:
        r = client.post("/api/projects", data={"mode": "long_form_extraction", "formats": "9:16,1:1", "min_dur": 8, "max_dur": 35, "n_min": 1},
                        files=[("files", ("podcast.mp4", f, "video/mp4")), ("files", ("podcast.transcript.json", tr, "application/json"))])
    pid = r.json()["id"]
    st = wait(client, pid)
    assert st["status"] == "ready", st
    assert all(s["state"] == "done" for k, s in st["stages"].items() if k != "plan") or st["overall"] == 1.0
    plan = client.get(f"/api/projects/{pid}/plan").json()
    assert plan["reels"] and plan["sources"][0]["id"] == "video1"
    assert client.get(f"/api/projects/{pid}/waveform/video1").json()["peaks"]
    assert client.get(f"/api/projects/{pid}/media/video1", headers={"Range": "bytes=0-99"}).status_code == 206


def test_demo_long_form_edit_and_render(client):
    pid = client.post("/api/demo", json={"mode": "long_form_extraction", "formats": ["9:16"]}).json()["id"]
    st = wait(client, pid)
    assert st["status"] == "ready", st
    plan = client.get(f"/api/projects/{pid}/plan").json()
    reel = plan["reels"][0]
    assert reel["framing"][0]["strategy"] == "smart_crop"
    segs = reel["timeline"]
    assert len(segs) >= 3

    # nudge in un silenzio: ok, e il piano si ricalcola (durata cambia di 1 frame)
    seg = segs[1]
    r = client.post(f"/api/projects/{pid}/edit", json={"reel_id": reel["id"], "ops": [{"op": "nudge", "segment_id": seg["id"], "edge": "in", "frames": -1}]})
    assert r.status_code == 200, r.text
    new = r.json()["reels"][0]
    assert abs(new["duration"] - (reel["duration"] + 1 / 30)) < 1e-3
    assert new["timeline"][1]["cut_in"]["reason"].endswith("+manuale")

    # nudge dentro il parlante: RIFIUTATO (non si possono mozzare parole dalla dashboard)
    r = client.post(f"/api/projects/{pid}/edit", json={"reel_id": reel["id"], "ops": [{"op": "nudge", "segment_id": seg["id"], "edge": "in", "frames": 25}]})
    assert r.status_code == 422 and "parlato" in r.json()["detail"]

    # rimozione di un segmento
    r = client.post(f"/api/projects/{pid}/edit", json={"reel_id": reel["id"], "ops": [{"op": "remove_segment", "segment_id": segs[2]["id"]}]})
    assert r.status_code == 200 and len(r.json()["reels"][0]["timeline"]) == len(segs) - 1

    # stile sottotitoli
    r = client.post(f"/api/projects/{pid}/edit", json={"reel_id": reel["id"], "ops": [{"op": "set_style", "preset": "clean", "uppercase": False}]})
    assert r.json()["reels"][0]["subtitles"]["uppercase"] is False

    # render draft e download
    assert client.post(f"/api/projects/{pid}/render", json={"quality": "draft"}).status_code == 200
    st = wait(client, pid, until=("done",))
    out = st["outputs"][0]
    assert out["file"].endswith("_draft.mp4") and out["caption"] and out["hashtags"] and out["transcript"]
    dl = client.get(f"/api/projects/{pid}/files/{out['file']}")
    assert dl.status_code == 200 and dl.headers["content-type"] == "video/mp4" and len(dl.content) > 10_000


def test_demo_script_mode_swap_take(client):
    pid = client.post("/api/demo", json={"mode": "script_assembly", "formats": ["16:9"]}).json()["id"]
    st = wait(client, pid)
    assert st["status"] == "ready", st
    plan = client.get(f"/api/projects/{pid}/plan").json()
    rep = plan["script_report"]
    assert [r["status"] for r in rep] == ["matched"] * 4
    unit1 = rep[1]
    alt = unit1["alternatives"][0]["take_id"]
    first = unit1["chosen_take"]
    r = client.post(f"/api/projects/{pid}/edit", json={"reel_id": "reel1", "ops": [{"op": "swap_take", "unit": 1, "take_id": alt}]})
    assert r.status_code == 200, r.text
    new = r.json()
    assert new["script_report"][1]["chosen_take"] == alt
    assert any(a["take_id"] == first for a in new["script_report"][1]["alternatives"])
    # lo script resta identico dopo lo swap
    from app.script_align import tokens
    from app.demo import SCRIPT_TEXT
    assert [t for w in new["reels"][0]["words"] for t in tokens(w["text"])] == tokens(SCRIPT_TEXT)
