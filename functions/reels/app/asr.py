"""Provider ASR con word-timestamps. L'ordine di preferenza è guidato dalle chiavi presenti."""
from __future__ import annotations

import json
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Protocol

import httpx

from .transcript import Transcript, from_deepgram, from_openai_verbose


class ASRUnavailable(RuntimeError):
    pass


class ASR(Protocol):
    name: str
    def transcribe(self, media_path: str, source_id: str, language: str | None) -> Transcript: ...


def _extract_audio(media_path: str, suffix: str = ".mp3") -> str:
    out = tempfile.NamedTemporaryFile(suffix=suffix, delete=False).name
    codec = ["-c:a", "libmp3lame", "-b:a", "64k"] if suffix == ".mp3" else ["-c:a", "flac"]
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", media_path, "-vn", "-ac", "1", "-ar", "16000", *codec, out], check=True)
    return out


class DeepgramASR:
    name = "deepgram"

    def __init__(self, key: str, model: str = "nova-2"):
        self.key, self.model = key, model

    def transcribe(self, media_path: str, source_id: str, language: str | None) -> Transcript:
        audio = _extract_audio(media_path)
        params = {"model": self.model, "smart_format": "true", "punctuate": "true", "diarize": "true",
                  "utterances": "false", "filler_words": "true"}
        params["language" if language else "detect_language"] = language or "true"
        with open(audio, "rb") as f:
            r = httpx.post("https://api.deepgram.com/v1/listen", params=params, content=f.read(),
                           headers={"Authorization": f"Token {self.key}", "Content-Type": "audio/mpeg"}, timeout=600)
        r.raise_for_status()
        return from_deepgram(r.json(), source_id)


class OpenAIWhisperASR:
    name = "openai-whisper"

    def __init__(self, key: str):
        self.key = key

    def transcribe(self, media_path: str, source_id: str, language: str | None) -> Transcript:
        return transcribe_chunks(media_path, source_id, lambda p: self._one(p, source_id, language), max_len=900.0)

    def _one(self, audio: str, source_id: str, language: str | None) -> Transcript:
        data = {"model": "whisper-1", "response_format": "verbose_json", "timestamp_granularities[]": "word"}
        if language:
            data["language"] = language
        with open(audio, "rb") as f:
            r = httpx.post("https://api.openai.com/v1/audio/transcriptions", data=data,
                           files={"file": ("audio.mp3", f, "audio/mpeg")},
                           headers={"Authorization": f"Bearer {self.key}"}, timeout=900)
        r.raise_for_status()
        return from_openai_verbose(r.json(), source_id)


class FasterWhisperASR:
    """Whisper locale: gratis, senza chiavi, gira su CPU (int8). I pesi si scaricano da HuggingFace al primo uso."""
    name = "faster-whisper"
    _models: dict[str, object] = {}

    def __init__(self, model: str | None = None):
        try:
            import faster_whisper  # noqa: F401
        except ImportError as e:
            raise ASRUnavailable("faster-whisper non installato (pip install faster-whisper)") from e
        self.model_name = model or os.environ.get("REELS_WHISPER_MODEL", "small")

    def _model(self):
        if self.model_name not in self._models:
            from faster_whisper import WhisperModel
            self._models[self.model_name] = WhisperModel(self.model_name, device="cpu", compute_type="int8")
        return self._models[self.model_name]

    def transcribe(self, media_path: str, source_id: str, language: str | None) -> Transcript:
        from .transcript import Word
        try:
            m = self._model()
        except Exception as e:      # tipicamente: rete verso huggingface.co bloccata
            raise ASRUnavailable(
                f"Impossibile caricare il modello Whisper '{self.model_name}' ({type(e).__name__}). "
                "Serve accesso a huggingface.co al primo avvio (poi è in cache), oppure imposta GROQ_API_KEY.") from e
        prompt = "Buongiorno a tutti. Oggi parliamo di un argomento interessante, e lo facciamo con calma." if language == "it" else None
        segs, info = m.transcribe(media_path, language=language, word_timestamps=True, vad_filter=True,
                                  condition_on_previous_text=False, initial_prompt=prompt)
        words = [Word(w.word.strip(), float(w.start), float(w.end), conf=float(getattr(w, "probability", 1.0)), source_id=source_id)
                 for sg in segs for w in (sg.words or []) if w.word.strip()]
        return Transcript(source_id, words, info.language, f"faster-whisper:{self.model_name}")


# ── API a file limitato: spezzo sui silenzi veri, mai a metà parola ─────────────

def plan_chunks(duration: float, env, max_len: float) -> list[tuple[float, float]]:
    """Confini ~ogni `max_len` s, spostati nel silenzio più lungo entro ±max_len/6."""
    bounds, t = [0.0], 0.0
    while duration - t > max_len * 1.1:
        target = t + max_len
        w = max_len / 6
        runs = [(a, b) for a, b in _silences(env, target - w, target + w)]
        t = (max(runs, key=lambda r: r[1] - r[0]) if runs else (target, target))
        t = (t[0] + t[1]) / 2
        bounds.append(t)
    bounds.append(duration)
    return list(zip(bounds, bounds[1:]))


def _silences(env, t0: float, t1: float) -> list[tuple[float, float]]:
    act = env.runs(t0, t1)
    edges = [t0] + [x for r in act for x in r] + [t1]
    return [(a, b) for a, b in zip(edges[::2], edges[1::2]) if b - a > 0.05]


def transcribe_chunks(media_path: str, source_id: str, send, max_len: float = 600.0) -> Transcript:
    """`send(chunk_mp3_path) -> Transcript` con tempi relativi al chunk. Ricompone con gli offset."""
    from .audio_analysis import compute_envelope
    from .media import probe, read_audio
    from .transcript import Word
    dur = probe(media_path).duration
    chunks = [(0.0, dur)] if dur <= max_len * 1.1 else plan_chunks(dur, compute_envelope(read_audio(media_path, 16000), 16000), max_len)
    words: list[Word] = []
    lang, prov = "it", "unknown"
    for a, b in chunks:
        out = tempfile.NamedTemporaryFile(suffix=".mp3", prefix=f"chunk_{int(a * 1000)}_", delete=False).name
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{a:.3f}", "-t", f"{b - a:.3f}", "-i", media_path, "-vn", "-ac", "1",
                        "-ar", "16000", "-c:a", "libmp3lame", "-b:a", "64k", out], check=True)
        t = send(out)
        lang, prov = t.language, t.provider
        words += [Word(w.text, w.start + a, w.end + a, w.speaker, w.conf, source_id) for w in t.words]
        os.unlink(out)
    return Transcript(source_id, words, lang, prov)


class GroqASR:
    """Whisper large-v3-turbo su Groq: free tier (serve solo una chiave gratuita, console.groq.com)."""
    name = "groq"

    def __init__(self, key: str, client: httpx.Client | None = None, model: str = "whisper-large-v3-turbo"):
        self.key, self.model = key, model
        self.http = client or httpx.Client(timeout=300)

    def _send(self, path: str, source_id: str, language: str | None) -> Transcript:
        data = {"model": self.model, "response_format": "verbose_json", "timestamp_granularities[]": "word", "temperature": "0"}
        if language:
            data["language"] = language
        for attempt in range(4):
            with open(path, "rb") as f:
                r = self.http.post("https://api.groq.com/openai/v1/audio/transcriptions", data=data,
                                   files={"file": ("audio.mp3", f, "audio/mpeg")}, headers={"Authorization": f"Bearer {self.key}"})
            if r.status_code == 429 and attempt < 3:       # limite del free tier: attendi e riprova
                import time
                time.sleep(min(float(r.headers.get("retry-after", 5)), 30)); continue
            r.raise_for_status()
            t = from_openai_verbose(r.json(), source_id)
            t.provider = "groq"
            return t
        raise RuntimeError("Groq: limite di richieste del free tier")

    def transcribe(self, media_path: str, source_id: str, language: str | None) -> Transcript:
        return transcribe_chunks(media_path, source_id, lambda p: self._send(p, source_id, language), max_len=600.0)


def sidecar_transcript(media_path: str, source_id: str) -> Transcript | None:
    """`video.mp4` + `video.transcript.json` (formato interno, Deepgram o OpenAI verbose)."""
    p = Path(media_path)
    for cand in (p.with_suffix(".transcript.json"), p.with_name(p.stem + ".transcript.json")):
        if cand.exists():
            j = json.loads(cand.read_text())
            if "words" in j and j["words"] and "text" in j["words"][0]:
                return Transcript.from_dict(j, source_id)
            if "results" in j:
                return from_deepgram(j, source_id)
            if "words" in j:
                return from_openai_verbose(j, source_id)
    return None


def default_asr() -> ASR:
    """REELS_ASR=groq|deepgram|openai|local forza la scelta; altrimenti: Groq → Deepgram → OpenAI → Whisper locale (gratis)."""
    forced = os.environ.get("REELS_ASR", "").lower()
    env = os.environ
    if forced == "local":
        return FasterWhisperASR()
    if (forced in ("", "groq")) and env.get("GROQ_API_KEY"):
        return GroqASR(env["GROQ_API_KEY"])
    if (forced in ("", "deepgram")) and env.get("DEEPGRAM_API_KEY"):
        return DeepgramASR(env["DEEPGRAM_API_KEY"])
    if (forced in ("", "openai")) and env.get("OPENAI_API_KEY"):
        return OpenAIWhisperASR(env["OPENAI_API_KEY"])
    try:
        return FasterWhisperASR()
    except ASRUnavailable:
        raise ASRUnavailable(
            "Nessun provider ASR disponibile. Gratis: installa faster-whisper (Whisper locale, nessuna chiave) "
            "oppure imposta GROQ_API_KEY (free tier). In alternativa carica una trascrizione (<video>.transcript.json).")


def transcribe(media_path: str, source_id: str, language: str | None = "it", asr: ASR | None = None) -> Transcript:
    t = sidecar_transcript(media_path, source_id)
    if t is not None:
        return t
    return (asr or default_asr()).transcribe(media_path, source_id, language)
