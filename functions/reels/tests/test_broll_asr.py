import json
from pathlib import Path

import httpx
import pytest

from app.asr import sidecar_transcript
from app.broll import PexelsClient, plan_windows, resolve
from app.pipeline import Options, Pipeline
from app.transcript import from_deepgram, from_openai_verbose


def test_deepgram_and_openai_parsers():
    dg = {"results": {"channels": [{"detected_language": "it", "alternatives": [{"words": [
        {"word": "ciao", "punctuated_word": "Ciao,", "start": 0.5, "end": 0.9, "confidence": 0.99, "speaker": 0},
        {"word": "mondo", "punctuated_word": "mondo.", "start": 1.0, "end": 1.4, "confidence": 0.98, "speaker": 1}]}]}]}}
    t = from_deepgram(dg, "v")
    assert [w.text for w in t.words] == ["Ciao,", "mondo."] and t.words[1].speaker == "S1" and t.language == "it"
    oa = {"language": "italian", "words": [{"word": "ciao", "start": 0.1, "end": 0.4}]}
    assert from_openai_verbose(oa, "v").words[0].end == 0.4


def test_sidecar_formats(tmp_path):
    v = tmp_path / "a.mp4"; v.write_bytes(b"x")
    (tmp_path / "a.transcript.json").write_text(json.dumps({"words": [{"word": "ciao", "start": 0.1, "end": 0.4}]}))
    assert sidecar_transcript(str(v), "a").words[0].text == "ciao"


def _mock_pexels():
    def handler(req: httpx.Request) -> httpx.Response:
        if req.url.host == "api.pexels.com":
            assert req.headers["Authorization"] == "KEY"
            q = req.url.params["query"]
            if q == "nulla":
                return httpx.Response(200, json={"videos": []})
            return httpx.Response(200, json={"videos": [{"id": 7, "video_files": [
                {"file_type": "video/mp4", "width": 360, "link": "https://cdn/x360.mp4"},
                {"file_type": "video/mp4", "width": 1080, "link": "https://cdn/x1080.mp4"}]}]})
        assert str(req.url) == "https://cdn/x1080.mp4"          # sceglie la risoluzione giusta
        return httpx.Response(200, content=b"VIDEO")
    return PexelsClient("KEY", httpx.Client(transport=httpx.MockTransport(handler)))


def test_pexels_client_downloads_best_file(tmp_path):
    p = _mock_pexels().fetch("segreto", tmp_path)
    assert p and p.read_bytes() == b"VIDEO" and p.name == "pexels_7.mp4"
    assert _mock_pexels().fetch("nulla", tmp_path) is None


def test_broll_planned_inside_long_segments_and_resolved(long_video, tmp_path):
    from conftest import BoxDetector
    plan = Pipeline("b", [("long", str(long_video["path"]))], Options(formats=["9:16"], n_min=1, n_max=2, broll=True),
                    transcripts={"long": long_video["transcript"]}, detector=BoxDetector(long_video["faces"]),
                    broll_provider=_mock_pexels(), work_dir=tmp_path).run()
    brolls = [b for r in plan.reels for b in r.broll]
    assert brolls, 'almeno una finestra di b-roll deve essere pianificata'
    for r in plan.reels:
        for b in r.broll:
            seg = next(s for s in r.timeline if s.out_start <= b.out_start < s.out_end)
            assert b.out_end <= seg.out_end - 0.9 and b.out_start >= seg.out_start + 1.1   # mai su inizio/fine segmento
            assert b.asset_path and Path(b.asset_path).exists()
    # senza chiave non si rompe nulla
    plan2 = Pipeline("b", [("long", str(long_video["path"]))], Options(formats=["9:16"], n_min=1, n_max=1, broll=True),
                     transcripts={"long": long_video["transcript"]}, detector=BoxDetector(long_video["faces"]), work_dir=tmp_path).run()
    assert "PEXELS_API_KEY" in plan2.diagnostics["broll"]
