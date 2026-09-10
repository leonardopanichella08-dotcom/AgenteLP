from __future__ import annotations

import json
import re
from typing import Any

from ..config import get_settings

_CORE = ("mission", "value_proposition", "icp", "market_context", "tone_of_voice")
_ALL = (*_CORE, "niche", "keywords_primary", "keywords_secondary")

_ONBOARD_TOOL = {
    "name": "submit_brand_profile",
    "description": "Sintesi strutturata del profilo/azienda + nicchia e keyword per la ricerca post.",
    "input_schema": {
        "type": "object",
        "properties": {
            "mission": {"type": "string", "description": "Cosa fa esattamente, in 1-2 frasi."},
            "value_proposition": {"type": "string"},
            "icp": {"type": "string", "description": "Ideal Customer Profile: chi e' il target primario."},
            "market_context": {"type": "string", "description": "In quale contesto/mercato opera."},
            "tone_of_voice": {"type": "string", "description": "3-5 aggettivi separati da virgola."},
            "niche": {
                "type": "string",
                "description": "La nicchia editoriale in 2-5 parole (es. 'AI per vendite B2B').",
            },
            "keywords_primary": {
                "type": "array",
                "items": {"type": "string"},
                "description": "4-6 keyword centrali della nicchia, ricercabili su LinkedIn.",
            },
            "keywords_secondary": {
                "type": "array",
                "items": {"type": "string"},
                "description": "4-6 keyword di contorno / temi adiacenti.",
            },
        },
        "required": list(_CORE),
    },
}


def _onboard_prompt(
    display_name: str,
    account_type: str,
    headline: str | None,
    industry: str | None,
    raw_about: str | None,
    kb_snippets: list[str] | None,
) -> str:
    kb = "\n".join(f"- {s}" for s in (kb_snippets or [])) or "(nessun documento)"
    return (
        "Analizza questo profilo LinkedIn e produci la scheda per un agente di "
        "content strategy. Concreto, niente buzzword. Nella stessa lingua del profilo.\n\n"
        f"Nome: {display_name} ({account_type})\n"
        f"Headline: {headline or '-'}\n"
        f"Settore: {industry or '-'}\n"
        f"Descrizione / esperienze / hashtag:\n{raw_about or '-'}\n\n"
        f"Documenti caricati:\n{kb}\n\n"
        "Oltre a mission/value prop/ICP/contesto/tono, deduci la NICCHIA editoriale "
        "e le KEYWORD (primarie e secondarie) con cui cercare i post piu' rilevanti "
        "per questo profilo: termini reali che userebbe chi scrive di questi temi."
    )


def synthesize_brand_profile(
    *,
    display_name: str,
    account_type: str,
    headline: str | None,
    industry: str | None,
    raw_about: str | None,
    kb_snippets: list[str] | None = None,
    hashtags: list[str] | None = None,
) -> dict[str, Any]:
    provider = get_settings().active_llm
    args = (display_name, account_type, headline, industry, raw_about, kb_snippets)
    try:
        if provider == "gemini":
            data = _synthesize_with_gemini(*args)
        elif provider == "anthropic":
            data = _synthesize_with_claude(*args)
        else:
            data = None
    except Exception:  # noqa: BLE001
        data = None
    if data is None:
        data = _synthesize_heuristic(display_name, account_type, headline, industry, raw_about, hashtags)
    return _fill_search_terms(data, headline, industry, hashtags)


def _synthesize_with_gemini(
    display_name: str,
    account_type: str,
    headline: str | None,
    industry: str | None,
    raw_about: str | None,
    kb_snippets: list[str] | None,
) -> dict[str, Any]:
    s = get_settings()
    schema = {
        "type": "OBJECT",
        "properties": {
            **{k: {"type": "STRING"} for k in _CORE},
            "niche": {"type": "STRING"},
            "keywords_primary": {"type": "ARRAY", "items": {"type": "STRING"}},
            "keywords_secondary": {"type": "ARRAY", "items": {"type": "STRING"}},
        },
        "required": list(_CORE),
    }
    from ..gemini_client import extract_text, generate_content

    body = {
        "contents": [
            {"role": "user", "parts": [{"text": _onboard_prompt(
                display_name, account_type, headline, industry, raw_about, kb_snippets
            )}]}
        ],
        "generationConfig": {
            "temperature": 0.4,
            "maxOutputTokens": 2200,
            "responseMimeType": "application/json",
            "responseSchema": schema,
        },
    }
    data = generate_content(api_key=s.gemini_api_key, model=s.gemini_model, body=body)
    out = json.loads(extract_text(data))
    out["generated_by_model"] = data.get("modelVersion") or s.gemini_model
    return out


def _synthesize_with_claude(
    display_name: str,
    account_type: str,
    headline: str | None,
    industry: str | None,
    raw_about: str | None,
    kb_snippets: list[str] | None,
) -> dict[str, Any]:
    from anthropic import Anthropic

    settings = get_settings()
    client = Anthropic(api_key=settings.anthropic_api_key)
    prompt = _onboard_prompt(display_name, account_type, headline, industry, raw_about, kb_snippets)
    prompt += "\n\nChiama submit_brand_profile."
    msg = client.messages.create(
        model=settings.anthropic_model,
        max_tokens=1200,
        tools=[_ONBOARD_TOOL],
        tool_choice={"type": "tool", "name": "submit_brand_profile"},
        messages=[{"role": "user", "content": prompt}],
    )
    tool_use = next(b for b in msg.content if b.type == "tool_use")
    data = dict(tool_use.input)
    data["generated_by_model"] = settings.anthropic_model
    return data


_STOP = {
    "the", "and", "for", "with", "che", "non", "per", "una", "uno", "del", "della",
    "di", "in", "a", "e", "il", "la", "le", "i", "gli", "un", "su", "da", "co",
}


def _tokens(*texts: str | None) -> list[str]:
    seen: list[str] = []
    for t in texts:
        for w in re.findall(r"[a-zA-Zàèéìòù0-9]{3,}", (t or "").lower()):
            if w not in _STOP and w not in seen:
                seen.append(w)
    return seen


def _synthesize_heuristic(
    display_name: str,
    account_type: str,
    headline: str | None,
    industry: str | None,
    raw_about: str | None,
    hashtags: list[str] | None = None,
) -> dict[str, Any]:
    about = (raw_about or "").strip()
    first_sentence = about.replace("\n", " ").split(". ")[0].strip().rstrip(".") if about else ""
    subject = "L'azienda" if account_type == "company" else display_name.split(" ")[0]
    field = industry or (headline.split("|")[0].strip() if headline else "il proprio settore")

    return {
        "mission": (first_sentence or (f"{subject}: {headline}." if headline else f"{subject} opera in {field}."))[:600],
        "value_proposition": (headline or first_sentence or f"{subject} porta risultati concreti in {field}.")[:600],
        "icp": f"Professionisti e decisori in {field} che cercano risultati misurabili e un approccio senza fuffa."[:600],
        "market_context": f"Mercato di {field}: molta offerta indifferenziata, poco posizionamento chiaro."[:600],
        "tone_of_voice": "autorevole, diretto, concreto, senza buzzword",
        "niche": field,
        "keywords_primary": (hashtags or [])[:6] or _tokens(headline, industry)[:6],
        "keywords_secondary": _tokens(first_sentence)[:6],
        "generated_by_model": "heuristic",
    }


def _fill_search_terms(
    data: dict[str, Any],
    headline: str | None,
    industry: str | None,
    hashtags: list[str] | None,
) -> dict[str, Any]:
    """Garantisce sempre niche + keyword valorizzate."""
    data.setdefault("niche", "")
    if not data.get("niche"):
        data["niche"] = industry or (headline.split("|")[0].strip() if headline else "") or "professionale"
    for key, fallback in (
        ("keywords_primary", (hashtags or [])[:6] or _tokens(headline, industry)[:6]),
        ("keywords_secondary", _tokens(industry, headline)[3:9]),
    ):
        v = data.get(key)
        if not isinstance(v, list) or not v:
            data[key] = fallback
        else:
            data[key] = [str(x).strip().lstrip("#") for x in v if str(x).strip()][:8]
    return data
