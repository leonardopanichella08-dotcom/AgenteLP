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


# ── ASR gratuito: Groq (HTTP simulato), chunking sui silenzi, Whisper locale (modello simulato) ──

def test_chunks_are_cut_in_real_silence_and_offsets_recomposed(podcast):
    """Un file lungo viene spezzato per le API a file limitato: i confini cadono nei silenzi, nessuna parola persa o duplicata."""
    from app.asr import plan_chunks, transcribe_chunks
    from app.audio_analysis import compute_envelope
    from app.media import probe, read_audio
    from app.transcript import Transcript, Word
    env = compute_envelope(read_audio(podcast["path"], 16000), 16000)
    dur = probe(podcast["path"]).duration
    chunks = plan_chunks(dur, env, max_len=12.0)
    assert len(chunks) >= 3 and chunks[0][0] == 0 and abs(chunks[-1][1] - dur) < 1e-6
    for (_, b), _n in zip(chunks, chunks[1:]):
        assert not env.active[env.idx(b)], f"confine di chunk {b:.2f}s su voce"

    truth = [w for w in podcast["truth"] if w.transcribed]
    def fake_send(path):                      # il "server" conosce le parole vere e il nome del chunk codifica l'inizio
        start = int(Path(path).name.split("_")[1]) / 1000
        end = next(b for a, b in chunks if abs(a - start) < 0.002)
        ws = [Word(w.text, w.start - start, w.end - start) for w in truth if start <= w.start and w.end <= end + 0.001]
        return Transcript("x", ws, "it", "fake")
    t = transcribe_chunks(str(podcast["path"]), "podcast", fake_send, max_len=12.0)
    assert [w.text for w in t.words] == [w.text for w in truth]
    assert max(abs(a.start - b.start) for a, b in zip(t.words, truth)) < 2e-3  # il nome-file del chunk tronca al ms


def test_groq_asr_request_and_free_tier_retry(podcast):
    from app.asr import GroqASR
    calls = []
    def handler(req: httpx.Request):
        calls.append(req)
        assert req.headers["Authorization"] == "Bearer K" and "api.groq.com/openai/v1/audio/transcriptions" in str(req.url)
        body = req.read()
        assert b"whisper-large-v3-turbo" in body and b"word" in body and b"language" in body
        if len(calls) == 1:
            return httpx.Response(429, headers={"retry-after": "0"}, json={"error": "rate"})
        return httpx.Response(200, json={"language": "italian", "words": [{"word": "Ciao", "start": 0.5, "end": 0.9}]})
    asr = GroqASR("K", httpx.Client(transport=httpx.MockTransport(handler)))
    t = asr.transcribe(str(podcast["path"]), "podcast", "it")
    assert len(calls) == 2 and t.words[0].text == "Ciao" and t.provider == "groq"


def test_default_asr_order_and_free_fallback(monkeypatch):
    from app import asr
    for k in ("GROQ_API_KEY", "DEEPGRAM_API_KEY", "OPENAI_API_KEY", "REELS_ASR"):
        monkeypatch.delenv(k, raising=False)
    assert asr.default_asr().name == "faster-whisper"           # nessuna chiave → gratis e locale
    monkeypatch.setenv("GROQ_API_KEY", "x")
    assert asr.default_asr().name == "groq"
    monkeypatch.setenv("REELS_ASR", "local")
    assert asr.default_asr().name == "faster-whisper"


def test_local_whisper_maps_words_and_reports_blocked_download(monkeypatch, podcast):
    """Mappatura parole dal modello (simulato: i pesi non sono scaricabili qui) e messaggio chiaro se il download fallisce."""
    import sys, types
    from app import asr
    seg = types.SimpleNamespace(words=[types.SimpleNamespace(word=" Ciao", start=0.5, end=0.9, probability=0.9),
                                       types.SimpleNamespace(word=" mondo.", start=1.0, end=1.4, probability=0.8)])
    class FakeModel:
        def __init__(self, *a, **k): pass
        def transcribe(self, *a, **k): return iter([seg]), types.SimpleNamespace(language="it")
    monkeypatch.setitem(sys.modules, "faster_whisper", types.SimpleNamespace(WhisperModel=FakeModel))
    asr.FasterWhisperASR._models.clear()
    t = asr.FasterWhisperASR("tiny").transcribe(str(podcast["path"]), "v", "it")
    assert [w.text for w in t.words] == ["Ciao", "mondo."] and t.provider == "faster-whisper:tiny"

    class Boom:
        def __init__(self, *a, **k): raise OSError("tunnel 403")
    monkeypatch.setitem(sys.modules, "faster_whisper", types.SimpleNamespace(WhisperModel=Boom))
    asr.FasterWhisperASR._models.clear()
    with pytest.raises(asr.ASRUnavailable) as e:
        asr.FasterWhisperASR("tiny").transcribe(str(podcast["path"]), "v", "it")
    assert "huggingface.co" in str(e.value) and "GROQ_API_KEY" in str(e.value)
