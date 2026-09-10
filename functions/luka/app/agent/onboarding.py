from __future__ import annotations

import json
from typing import Any

from ..config import get_settings

_FIELDS = ("mission", "value_proposition", "icp", "market_context", "tone_of_voice")

_ONBOARD_TOOL = {
    "name": "submit_brand_profile",
    "description": "Sintesi strutturata del profilo/azienda per l'agente Luka.",
    "input_schema": {
        "type": "object",
        "properties": {
            "mission": {"type": "string", "description": "Cosa fa esattamente, in 1-2 frasi."},
            "value_proposition": {"type": "string"},
            "icp": {"type": "string", "description": "Ideal Customer Profile: chi e' il target primario."},
            "market_context": {"type": "string", "description": "In quale contesto/mercato opera."},
            "tone_of_voice": {"type": "string", "description": "3-5 aggettivi separati da virgola."},
        },
        "required": list(_FIELDS),
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
        "Analizza il seguente profilo LinkedIn e sintetizza la scheda per un agente "
        "di content strategy. Sii concreto, niente buzzword.\n\n"
        f"Nome: {display_name} ({account_type})\n"
        f"Headline: {headline or '-'}\n"
        f"Industry: {industry or '-'}\n"
        f"Descrizione/bio/esperienze:\n{raw_about or '-'}\n\n"
        f"Estratti da documenti caricati:\n{kb}\n"
    )


def synthesize_brand_profile(
    *,
    display_name: str,
    account_type: str,
    headline: str | None,
    industry: str | None,
    raw_about: str | None,
    kb_snippets: list[str] | None = None,
) -> dict[str, Any]:
    provider = get_settings().active_llm
    args = (display_name, account_type, headline, industry, raw_about, kb_snippets)
    try:
        if provider == "gemini":
            return _synthesize_with_gemini(*args)
        if provider == "anthropic":
            return _synthesize_with_claude(*args)
    except Exception:  # noqa: BLE001
        pass
    return _synthesize_heuristic(display_name, account_type, headline, industry, raw_about)


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
            k: {"type": "STRING"} for k in _FIELDS
        },
        "required": list(_FIELDS),
    }
    from ..gemini_client import extract_text, generate_content

    body = {
        "contents": [
            {
                "role": "user",
                "parts": [{"text": _onboard_prompt(
                    display_name, account_type, headline, industry, raw_about, kb_snippets
                )}],
            }
        ],
        "generationConfig": {
            "temperature": 0.4,
            "maxOutputTokens": 2000,
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

    kb = "\n".join(f"- {s}" for s in (kb_snippets or [])) or "(nessun documento)"
    prompt = (
        "Analizza il seguente profilo LinkedIn e sintetizza la scheda per un agente "
        "di content strategy. Sii concreto, niente buzzword.\n\n"
        f"Nome: {display_name} ({account_type})\n"
        f"Headline: {headline or '-'}\n"
        f"Industry: {industry or '-'}\n"
        f"Descrizione/bio/esperienze:\n{raw_about or '-'}\n\n"
        f"Estratti da documenti caricati:\n{kb}\n\n"
        "Chiama submit_brand_profile."
    )
    msg = client.messages.create(
        model=settings.anthropic_model,
        max_tokens=900,
        tools=[_ONBOARD_TOOL],
        tool_choice={"type": "tool", "name": "submit_brand_profile"},
        messages=[{"role": "user", "content": prompt}],
    )
    tool_use = next(b for b in msg.content if b.type == "tool_use")
    data = dict(tool_use.input)
    data["generated_by_model"] = settings.anthropic_model
    return data


def _synthesize_heuristic(
    display_name: str,
    account_type: str,
    headline: str | None,
    industry: str | None,
    raw_about: str | None,
) -> dict[str, Any]:
    about = (raw_about or "").strip()
    first_sentence = ""
    if about:
        first_sentence = about.replace("\n", " ").split(". ")[0].strip().rstrip(".")

    subject = "L'azienda" if account_type == "company" else display_name.split(" ")[0]
    field = industry or (headline.split("|")[0].strip() if headline else "il proprio settore")

    mission = (
        first_sentence
        or (f"{subject} opera in {field}." if not headline else f"{subject}: {headline}.")
    )
    value_prop = (
        headline
        or first_sentence
        or f"{subject} aiuta i propri clienti a ottenere risultati concreti in {field}."
    )
    icp = (
        f"Professionisti e decisori in {field} che cercano risultati misurabili "
        "e un approccio senza fuffa."
    )
    market_context = (
        f"Mercato di {field}: attenzione a costi, tempi di adozione e ritorno concreto; "
        "molta offerta indifferenziata, poco posizionamento chiaro."
    )
    tone = "autorevole, diretto, concreto, senza buzzword"

    return {
        "mission": mission[:600],
        "value_proposition": value_prop[:600],
        "icp": icp[:600],
        "market_context": market_context[:600],
        "tone_of_voice": tone,
        "generated_by_model": "heuristic",
    }
