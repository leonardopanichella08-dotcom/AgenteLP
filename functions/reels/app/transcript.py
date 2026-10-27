"""Modello di trascrizione word-level e parser dei formati dei provider ASR."""
from __future__ import annotations

import re
import unicodedata
from dataclasses import asdict, dataclass, field

from .config import FILLERS_IT


@dataclass
class Word:
    text: str                  # come scritto dall'ASR (con punteggiatura)
    start: float
    end: float
    speaker: str | None = None
    conf: float = 1.0
    source_id: str = ""

    @property
    def mid(self) -> float:
        return (self.start + self.end) / 2

    @property
    def norm(self) -> str:
        return normalize(self.text)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Transcript:
    source_id: str
    words: list[Word]
    language: str = "it"
    provider: str = "unknown"

    @property
    def text(self) -> str:
        return " ".join(w.text for w in self.words)

    def to_dict(self) -> dict:
        return {"source_id": self.source_id, "language": self.language, "provider": self.provider,
                "words": [w.to_dict() for w in self.words]}

    @classmethod
    def from_dict(cls, d: dict, source_id: str | None = None) -> "Transcript":
        sid = source_id or d.get("source_id", "")
        words = [Word(text=w["text"], start=float(w["start"]), end=float(w["end"]),
                      speaker=w.get("speaker"), conf=float(w.get("conf", 1.0)), source_id=sid)
                 for w in d["words"]]
        return cls(source_id=sid, words=words, language=d.get("language", "it"),
                   provider=d.get("provider", "import"))


def normalize(s: str) -> str:
    """minuscolo, senza punteggiatura; mantiene lettere accentate e cifre."""
    s = unicodedata.normalize("NFKC", s).lower()
    return re.sub(r"[^\w]+", "", s, flags=re.UNICODE)


def is_filler(w: Word) -> bool:
    return w.norm in FILLERS_IT


def lexical(words: list[Word]) -> list[Word]:
    """Parole vere: via gli intercalari non lessicali (eh, ehm, mmh...)."""
    return [w for w in words if not is_filler(w) and w.norm]


# ── parser formati provider ───────────────────────────────────────────────

def from_deepgram(j: dict, source_id: str) -> Transcript:
    alt = j["results"]["channels"][0]["alternatives"][0]
    words = [Word(text=w.get("punctuated_word", w["word"]), start=w["start"], end=w["end"],
                  speaker=f"S{w['speaker']}" if "speaker" in w else None,
                  conf=w.get("confidence", 1.0), source_id=source_id)
             for w in alt["words"]]
    lang = j.get("results", {}).get("channels", [{}])[0].get("detected_language", "it")
    return Transcript(source_id, words, lang, "deepgram")


def from_openai_verbose(j: dict, source_id: str) -> Transcript:
    """OpenAI whisper-1 con response_format=verbose_json + timestamp_granularities[]=word."""
    words = [Word(text=w["word"], start=w["start"], end=w["end"], source_id=source_id) for w in j["words"]]
    return Transcript(source_id, words, j.get("language", "it"), "openai-whisper")
