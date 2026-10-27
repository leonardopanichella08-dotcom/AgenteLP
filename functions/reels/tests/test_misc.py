import json
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.llm import ClaudeEditor, system_prompt, validate_picks
from app.media import probe
from app.pipeline import Options, Pipeline
from app.render import render_reel
from app.schemas import EditPlan, json_schema
from app.subtitles import build_ass, chunk_words
from conftest import BoxDetector


@pytest.fixture(scope="module")
def plan_b(podcast):
    return Pipeline("p", [("podcast", str(podcast["path"]))],
                    Options(formats=["9:16", "16:9"], min_dur=8, max_dur=35, n_min=1, reframe="blur_pad"),
                    transcripts={"podcast": podcast["transcript"]}).run()


def test_schema_roundtrip_and_export(plan_b):
    js = json.loads(plan_b.model_dump_json())
    assert EditPlan.model_validate(js).reels[0].id == plan_b.reels[0].id
    sch = json_schema()
    assert "reels" in sch["properties"] and "$defs" in sch


def test_subtitles_ass_is_well_formed(plan_b):
    r = plan_b.reels[0]
    ass = build_ass(r.words, r.subtitles, 1080, 1920, fonts_ok_emoji=False)
    events = [l for l in ass.splitlines() if l.startswith("Dialogue:")]
    assert len(events) >= len(r.words)
    starts = [l.split(",")[1] for l in events]
    assert starts == sorted(starts)
    # nessun evento oltre la fine del reel (+tolleranza di coda)
    def secs(t): h, m, s = t.split(":"); return int(h) * 3600 + int(m) * 60 + float(s)
    assert max(secs(l.split(",")[2]) for l in events) <= r.duration + 0.3
    # posizione dentro la safe-zone 9:16 (sotto il 10% e sopra il 78%)
    ys = {int(l.split("\\pos(")[1].split(",")[1].split(")")[0]) for l in events}
    assert all(0.1 * 1920 < y < 0.78 * 1920 for y in ys)
    # righe corte: max 3 parole
    assert all(len(c) <= 3 for c in chunk_words(r.words, 3, 40))


def test_blur_pad_render_keeps_full_frame_without_black_bars(plan_b, tmp_path):
    r = plan_b.reels[0]
    fr = next(f for f in r.framing if f.format_id == "9:16")
    assert fr.strategy == "blur_pad"
    out = render_reel(plan_b, r, plan_b.exports[0], tmp_path / "b.mp4", tmp_path / "w", quality="draft")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", "3", "-i", str(out), "-frames:v", "1", str(tmp_path / "f.png")], check=True)
    from PIL import Image
    import numpy as np
    im = np.asarray(Image.open(tmp_path / "f.png").convert("L")).astype(float)
    top, bottom = im[: im.shape[0] // 8], im[-im.shape[0] // 8:]
    assert top.mean() > 25            # sfondo = il muro della scena sfocato, non banda nera (nero limited-range < 16)
    assert top.std() < 40             # ed e' sfocato (poca varianza)
    assert bottom.mean() < top.mean() # il pavimento (piu' scuro) c'e': il fondo e' contenuto vero, non un riempimento


def test_broll_overlay_and_sfx_are_rendered(plan_b, tmp_path):
    r = plan_b.reels[0].model_copy(deep=True)
    clip = tmp_path / "broll.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "color=c=red:s=320x180:r=30:d=1", "-pix_fmt", "yuv420p", str(clip)], check=True)
    from app.schemas import Broll
    r.broll = [Broll(out_start=2.0, out_end=3.5, query="x", asset_path=str(clip), provider="local")]
    assert r.sfx, "il piano deve contenere SFX"
    out = render_reel(plan_b, r, plan_b.exports[0], tmp_path / "br.mp4", tmp_path / "w", quality="draft")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", "2.5", "-i", str(out), "-frames:v", "1", str(tmp_path / "f.png")], check=True)
    from PIL import Image
    import numpy as np
    px = np.asarray(Image.open(tmp_path / "f.png").convert("RGB")).reshape(-1, 3).mean(0)
    assert px[0] > 150 and px[1] < 90        # dominante rossa: b-roll visibile


class StubClient:
    def __init__(self, payload):
        self.payload, self.calls = payload, []
        self.messages = SimpleNamespace(create=self._create)

    def _create(self, **kw):
        self.calls.append(kw)
        return SimpleNamespace(content=[SimpleNamespace(type="tool_use", input=self.payload)])


def test_llm_picks_are_validated_and_cut_by_code(long_video):
    """L'LLM dà ID di frase (anche sbagliati); i tempi li decide il codice."""
    picks = {"clips": [
        {"start_sentence": 0, "end_sentence": 3, "virality_score": 91, "reasons": ["gancio"], "hook_text": "x", "title": "T1", "caption": "C1", "hashtags": ["#a"], "keywords": ["triplicato"]},
        {"start_sentence": 2, "end_sentence": 5, "virality_score": 80, "reasons": ["sovrapposto"], "hook_text": "x", "title": "T2", "caption": "C2", "hashtags": []},
        {"start_sentence": 9, "end_sentence": 999, "virality_score": 70, "reasons": ["id inesistente"], "hook_text": "x", "title": "T3", "caption": "C3", "hashtags": []},
    ]}
    assert [p["title"] for p in validate_picks(picks["clips"], 24)] == ["T1"]
    client = StubClient(picks)
    llm = ClaudeEditor(client=client, model="claude-sonnet-5-5")
    plan = Pipeline("l", [("long", str(long_video["path"]))], Options(formats=["9:16"], n_min=1, n_max=2, min_dur=10, max_dur=60),
                    transcripts={"long": long_video["transcript"]}, detector=BoxDetector(long_video["faces"]), llm=llm).run()
    assert client.calls and client.calls[0]["tool_choice"]["name"] == "submit_clips"
    assert "tagli" in client.calls[0]["system"].lower()
    titles = [r.title for r in plan.reels]
    assert "T1" in titles
    r1 = next(r for r in plan.reels if r.title == "T1")
    assert r1.social.caption == "C1" and r1.virality.score == 91


def test_system_prompt_contains_hard_rules():
    sp = system_prompt()
    for key in ("MODALITÀ A", "MODALITÀ B", "id di frase", "mai timestamp", "submit_clips"):
        assert key.lower() in sp.lower(), key
