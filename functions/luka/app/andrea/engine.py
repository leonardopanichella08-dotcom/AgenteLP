"""Motore di esecuzione A.I.R.S. — chiamate LLM per mappa, iterazioni, finale."""

from __future__ import annotations

import json
from typing import Any

from ..config import get_settings
from . import prompts

MAX_TOKENS = 6000


def _gemini_schema(schema: dict) -> dict:
    """Normalizza un JSON-schema al sottoinsieme accettato da Gemini."""
    allowed = {"type", "description", "enum", "items", "properties", "required", "nullable"}
    out: dict[str, Any] = {}
    for k, v in schema.items():
        if k not in allowed:
            continue
        if k == "type" and isinstance(v, str):
            out[k] = v.upper()
        elif k == "properties":
            out[k] = {pk: _gemini_schema(pv) for pk, pv in v.items()}
        elif k == "items":
            out[k] = _gemini_schema(v)
        else:
            out[k] = v
    return out


def _anthropic_schema(schema: dict) -> dict:
    """Gemini usa type in MAIUSCOLO; Anthropic vuole minuscolo."""
    out: dict[str, Any] = {}
    for k, v in schema.items():
        if k == "type" and isinstance(v, str):
            out[k] = v.lower()
        elif k == "properties":
            out[k] = {pk: _anthropic_schema(pv) for pk, pv in v.items()}
        elif k == "items":
            out[k] = _anthropic_schema(v)
        else:
            out[k] = v
    return out


def json_call(prompt: str, schema: dict, *, temperature: float = 0.75) -> tuple[dict, str]:
    """Ritorna (output_dict, model_used). Usa il provider LLM attivo."""
    s = get_settings()
    provider = s.active_llm
    if provider == "gemini":
        from ..gemini_client import extract_text, generate_content

        body = {
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": MAX_TOKENS,
                "responseMimeType": "application/json",
                "responseSchema": _gemini_schema(schema),
            },
        }
        data = generate_content(api_key=s.gemini_api_key, model=s.gemini_model, body=body, timeout=180)
        text = extract_text(data)
        return json.loads(text), data.get("modelVersion") or s.gemini_model
    if provider == "anthropic":
        from anthropic import Anthropic

        client = Anthropic(api_key=s.anthropic_api_key)
        tool = {
            "name": "submit",
            "description": "Invia il risultato strutturato.",
            "input_schema": _anthropic_schema(schema),
        }
        msg = client.messages.create(
            model=s.anthropic_model,
            max_tokens=MAX_TOKENS,
            temperature=temperature,
            tools=[tool],
            tool_choice={"type": "tool", "name": "submit"},
            messages=[{"role": "user", "content": prompt}],
        )
        block = next(b for b in msg.content if b.type == "tool_use")
        return dict(block.input), s.anthropic_model
    raise RuntimeError(
        "ANDREA richiede un modello linguistico: imposta GEMINI_API_KEY (gratis) "
        "o ANTHROPIC_API_KEY."
    )


# ─────────────────────────── step del protocollo ───────────────────────────


def build_systemic_map(startup_name: str, input_text: str, laws: list[dict]) -> tuple[dict, str]:
    prompt = prompts.systemic_map_prompt(startup_name, input_text, laws)
    return json_call(prompt, prompts.MAP_SCHEMA, temperature=0.6)


def run_iteration(
    *,
    startup_name: str,
    index: int,
    total: int,
    prev_version: str,
    systemic_map: str,
    lethal_flaws: list[dict],
    laws: list[dict],
    prev_flaws: list[str],
) -> tuple[dict, str]:
    prompt = prompts.iteration_prompt(
        startup_name, index, total, prev_version, systemic_map,
        lethal_flaws, laws, prev_flaws,
    )
    return json_call(prompt, prompts.ITERATION_SCHEMA, temperature=0.8)


def finalize(startup_name: str, final_version: str, all_flaws: list[str]) -> tuple[dict, str]:
    prompt = prompts.finalize_prompt(startup_name, final_version, all_flaws)
    return json_call(prompt, prompts.FINALIZE_SCHEMA, temperature=0.55)
