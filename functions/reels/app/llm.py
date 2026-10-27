"""Livello LLM (Claude): decisioni *editoriali* su ID di frasi, mai su timestamp.

L'LLM sceglie quali frasi formano un reel e perché; i punti di taglio esatti
li calcola il codice sul segnale audio (vedi cutting.py). Così un LLM che
"sbaglia di mezzo secondo" non può mozzare una parola.
Senza ANTHROPIC_API_KEY l'agente funziona comunque con l'euristica offline.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Protocol

from .config import LLM_MODEL
from .cutting import Sentence

PROMPT_PATH = Path(__file__).parent / "prompts" / "system_prompt.md"


def system_prompt() -> str:
    return PROMPT_PATH.read_text(encoding="utf-8")


SELECT_TOOL = {
    "name": "submit_clips",
    "description": "Consegna i reel scelti. Usa SOLO id di frase esistenti; start_sentence <= end_sentence.",
    "input_schema": {
        "type": "object",
        "properties": {"clips": {"type": "array", "items": {
            "type": "object",
            "properties": {
                "start_sentence": {"type": "integer"}, "end_sentence": {"type": "integer"},
                "virality_score": {"type": "integer", "minimum": 0, "maximum": 100},
                "reasons": {"type": "array", "items": {"type": "string"}},
                "hook_text": {"type": "string", "description": "la frase-gancio dei primi 3 secondi"},
                "title": {"type": "string"}, "caption": {"type": "string"},
                "hashtags": {"type": "array", "items": {"type": "string"}},
                "keywords": {"type": "array", "items": {"type": "string"}, "description": "parole da evidenziare nei sottotitoli"},
            },
            "required": ["start_sentence", "end_sentence", "virality_score", "reasons", "hook_text", "title", "caption", "hashtags"],
        }}},
        "required": ["clips"],
    },
}

ENRICH_TOOL = {
    "name": "submit_copy",
    "description": "Copy social e indicazioni di enfasi per un reel già montato.",
    "input_schema": {
        "type": "object",
        "properties": {
            "title": {"type": "string"}, "caption": {"type": "string"},
            "hashtags": {"type": "array", "items": {"type": "string"}},
            "keywords": {"type": "array", "items": {"type": "string"}},
            "broll_queries": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["title", "caption", "hashtags", "keywords"],
    },
}


class LLM(Protocol):
    def select_clips(self, sentences: list[Sentence], k_min: int, k_max: int, min_s: float, max_s: float,
                     language: str) -> list[dict]: ...
    def enrich(self, transcript: str, language: str) -> dict: ...


class ClaudeEditor:
    def __init__(self, client: Any | None = None, model: str | None = None):
        if client is None:
            import anthropic
            client = anthropic.Anthropic()
        self.client, self.model = client, model or LLM_MODEL

    def _call(self, tool: dict, user: str, max_tokens: int = 4000) -> dict:
        resp = self.client.messages.create(
            model=self.model, max_tokens=max_tokens, system=system_prompt(),
            tools=[tool], tool_choice={"type": "tool", "name": tool["name"]},
            messages=[{"role": "user", "content": user}])
        for block in resp.content:
            if getattr(block, "type", None) == "tool_use":
                return dict(block.input)
        raise RuntimeError("Il modello non ha restituito il tool atteso")

    def select_clips(self, sentences, k_min, k_max, min_s, max_s, language):
        lines = [f"S{s.id} [{s.start:.1f}-{s.end:.1f}s] ({s.speaker or '?'}) "
                 f"{'|pausa prima' if s.lead_pause >= 0.25 else '|attacco senza pausa'} {s.text}" for s in sentences]
        user = (f"MODALITÀ B — estrazione. Lingua: {language}. Scegli da {k_min} a {k_max} reel; "
                f"ognuno è una sequenza CONSECUTIVA di frasi con durata totale tra {min_s:.0f} e {max_s:.0f} secondi "
                f"(il montaggio rimuoverà le pause, quindi conta la durata parlata). "
                f"Non sovrapporre i reel.\n\nTRASCRITTO:\n" + "\n".join(lines))
        return self._call(SELECT_TOOL, user)["clips"]

    def enrich(self, transcript, language):
        return self._call(ENRICH_TOOL, f"Lingua: {language}. Trascritto del reel:\n{transcript}", 1500)


def validate_picks(picks: list[dict], n_sentences: int) -> list[dict]:
    """Scarta scelte con id inesistenti, invertiti o sovrapposti. Mai fidarsi dell'output di un LLM."""
    ok: list[dict] = []
    for p in picks:
        try:
            a, b = int(p["start_sentence"]), int(p["end_sentence"])
        except (KeyError, TypeError, ValueError):
            continue
        if not (0 <= a <= b < n_sentences):
            continue
        if any(not (b < q["start_sentence"] or a > q["end_sentence"]) for q in ok):
            continue
        ok.append({**p, "start_sentence": a, "end_sentence": b})
    return ok


def get_llm() -> LLM | None:
    if os.environ.get("ANTHROPIC_API_KEY"):
        return ClaudeEditor()
    return None
