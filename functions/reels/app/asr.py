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
        audio = _extract_audio(media_path)
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
    name = "faster-whisper"

    def __init__(self, model: str = "small"):
        try:
            from faster_whisper import WhisperModel   # noqa: F401
        except ImportError as e:
            raise ASRUnavailable("faster-whisper non installato") from e
        self.model_name = model

    def transcribe(self, media_path: str, source_id: str, language: str | None) -> Transcript:
        from faster_whisper import WhisperModel
        from .transcript import Word
        m = WhisperModel(self.model_name, compute_type="int8")
        segs, info = m.transcribe(media_path, language=language, word_timestamps=True, vad_filter=False)
        words = [Word(w.word.strip(), w.start, w.end, conf=w.probability, source_id=source_id)
                 for s in segs for w in (s.words or [])]
        return Transcript(source_id, words, info.language, "faster-whisper")


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
    if os.environ.get("DEEPGRAM_API_KEY"):
        return DeepgramASR(os.environ["DEEPGRAM_API_KEY"])
    if os.environ.get("OPENAI_API_KEY"):
        return OpenAIWhisperASR(os.environ["OPENAI_API_KEY"])
    try:
        return FasterWhisperASR()
    except ASRUnavailable:
        raise ASRUnavailable(
            "Nessun provider ASR configurato. Imposta DEEPGRAM_API_KEY o OPENAI_API_KEY, "
            "installa faster-whisper, oppure carica una trascrizione (<video>.transcript.json).")


def transcribe(media_path: str, source_id: str, language: str | None = "it", asr: ASR | None = None) -> Transcript:
    t = sidecar_transcript(media_path, source_id)
    if t is not None:
        return t
    return (asr or default_asr()).transcribe(media_path, source_id, language)
