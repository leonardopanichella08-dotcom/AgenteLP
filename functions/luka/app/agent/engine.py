from __future__ import annotations

import json
import re
from typing import Any

import httpx

from ..config import get_settings
from .prompt import (
    PROMPT_VERSION,
    SUBMIT_TOOL,
    BrandContext,
    DiscoveredPost,
    build_system_blocks,
    build_user_message,
)

MAX_TOKENS = 1600
_ENGAGEMENT_SCHEMA = SUBMIT_TOOL["input_schema"]


def generate_engagement(
    ctx: BrandContext,
    post: DiscoveredPost,
    rag_snippets: list[str] | None = None,
    n_comment_variants: int = 2,
) -> dict[str, Any]:
    """Ritorna {prompt_version, model, tokens_input, tokens_output, output}.

    `output` = dict conforme allo schema SUBMIT_TOOL.
    Provider: Gemini (gratis) -> Anthropic (a consumo) -> demo generator.
    Un errore del provider LLM ricade sempre sul demo: l'app non si rompe mai.
    """
    provider = get_settings().active_llm
    try:
        if provider == "gemini":
            return _generate_with_gemini(ctx, post, rag_snippets, n_comment_variants)
        if provider == "anthropic":
            return _generate_with_claude(ctx, post, rag_snippets, n_comment_variants)
    except Exception as exc:  # noqa: BLE001
        demo = _demo_generate(ctx, post, n_comment_variants)
        demo["model"] = f"demo (fallback {provider}: {type(exc).__name__})"
        return demo
    return _demo_generate(ctx, post, n_comment_variants)


# ──────────────────────────────── Gemini (gratis) ────────────────────────────────


def _gemini_prompt(ctx: BrandContext, post: DiscoveredPost, rag: list[str] | None, n: int) -> tuple[str, str]:
    blocks = build_system_blocks(ctx, rag)
    system_text = "\n\n".join(b["text"] for b in blocks)
    user_text = (
        build_user_message(post, n)
        + "\n\nRispondi SOLO con un oggetto JSON conforme a questo schema "
        "(nessun testo attorno):\n"
        + json.dumps(_ENGAGEMENT_SCHEMA, ensure_ascii=False)
    )
    return system_text, user_text


def _generate_with_gemini(
    ctx: BrandContext,
    post: DiscoveredPost,
    rag_snippets: list[str] | None,
    n: int,
) -> dict[str, Any]:
    s = get_settings()
    system_text, user_text = _gemini_prompt(ctx, post, rag_snippets, n)
    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{s.gemini_model}:generateContent"
    )
    body = {
        "systemInstruction": {"parts": [{"text": system_text}]},
        "contents": [{"role": "user", "parts": [{"text": user_text}]}],
        "generationConfig": {
            "temperature": 0.9,
            "maxOutputTokens": MAX_TOKENS,
            "responseMimeType": "application/json",
            "responseSchema": _gemini_schema(_ENGAGEMENT_SCHEMA),
        },
    }
    with httpx.Client(timeout=60) as c:
        r = c.post(url, params={"key": s.gemini_api_key}, json=body)
        r.raise_for_status()
        data = r.json()

    parts = data["candidates"][0]["content"]["parts"]
    text = "".join(p.get("text", "") for p in parts)
    output = json.loads(text)
    usage = data.get("usageMetadata", {})
    return {
        "prompt_version": PROMPT_VERSION,
        "model": s.gemini_model,
        "tokens_input": usage.get("promptTokenCount"),
        "tokens_output": usage.get("candidatesTokenCount"),
        "output": _coerce_output(output),
    }


def _gemini_schema(schema: dict) -> dict:
    """Adatta il JSON-Schema in ingresso al sottoinsieme accettato da Gemini."""
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


def _coerce_output(output: Any) -> dict[str, Any]:
    if not isinstance(output, dict):
        return {"skip": True, "skip_reason": "output non valido", "comments": []}
    output.setdefault("skip", False)
    output.setdefault("comments", [])
    return output


# ──────────────────────────────── Claude ────────────────────────────────


def _generate_with_claude(
    ctx: BrandContext,
    post: DiscoveredPost,
    rag_snippets: list[str] | None,
    n: int,
) -> dict[str, Any]:
    from anthropic import Anthropic

    settings = get_settings()
    client = Anthropic(api_key=settings.anthropic_api_key)

    msg = client.messages.create(
        model=settings.anthropic_model,
        max_tokens=MAX_TOKENS,
        system=build_system_blocks(ctx, rag_snippets),
        tools=[SUBMIT_TOOL],
        tool_choice={"type": "tool", "name": "submit_engagement"},
        messages=[{"role": "user", "content": build_user_message(post, n)}],
    )
    tool_use = next(b for b in msg.content if b.type == "tool_use")
    return {
        "prompt_version": PROMPT_VERSION,
        "model": settings.anthropic_model,
        "tokens_input": msg.usage.input_tokens,
        "tokens_output": msg.usage.output_tokens,
        "output": tool_use.input,
    }


# ─────────────────────────────── Demo mode ───────────────────────────────
# Genera output plausibile e coerente col post + contesto, senza LLM.
# Serve a far funzionare l'app end-to-end a costo zero.

_HOOKS = ["reframe", "data_point", "contrarian", "question"]
_STRONG = ("non ", "mai ", "sbagli", "invece", "eppure", "verita", "scomod")


def _first_claim(text: str) -> str:
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", text.strip()) if s.strip()]
    candidates = sentences[:4]
    for s in candidates:
        low = s.lower()
        if 30 <= len(s) <= 160 and not s.endswith("?") and (
            any(m in low for m in _STRONG) or re.search(r"\d", s)
        ):
            return s.rstrip(".")
    for s in candidates:
        if 30 <= len(s) <= 200 and not s.endswith("?"):
            return s.rstrip(".")
    return text[:140].rstrip(".")


def _domain(ctx: BrandContext) -> str:
    """Breve etichetta di dominio per ancorare il commento, senza pubblicita'."""
    raw = ctx.industry if getattr(ctx, "industry", None) else ""
    if not raw and ctx.headline:
        raw = ctx.headline.split("|")[0].split("-")[0]
    raw = (raw or ctx.icp or "vendite B2B").strip().rstrip(".")
    raw = re.split(r"[.:;]", raw)[0]
    return (raw[:60] or "vendite B2B").lower()


def _demo_generate(ctx: BrandContext, post: DiscoveredPost, n: int) -> dict[str, Any]:
    claim = _first_claim(post.text)
    dom = _domain(ctx)
    who = post.author_name.split(" ")[0]

    templates = [
        (
            "reframe",
            f"Il punto vero qui non e' \"{claim.lower()}\", ma cosa lo rende cosi' "
            f"difficile da applicare davvero. Lavorando ogni giorno con team di {dom} "
            f"vedo che il blocco non e' capire il principio: e' avere il coraggio di "
            f"dire di no a meta' delle occasioni. {who}, tu dove metti la linea?",
            "Sposta il focus dal 'cosa' al 'perche' e' raro' e apre con una domanda "
            "diretta all'autore.",
        ),
        (
            "data_point",
            f"Confermo dall'esperienza sul campo. Sugli stessi problemi, nel mondo {dom}, "
            f"il risultato non arriva dal fare piu' cose ma dal toglierne: meno volume, "
            f"piu' segnale, ciclo piu' corto. La parte scomoda e' spiegarlo a chi misura "
            f"tutto in quantita'. A te e' successo lo stesso?",
            "Porta un'esperienza coerente col contesto dell'utente senza citarlo come "
            "pubblicita', e chiude con domanda aperta.",
        ),
        (
            "contrarian",
            f"Aggiungo una nota controcorrente: \"{claim.lower()}\" regge finche' non "
            f"diventa uno slogan. L'ho visto ridursi all'ennesima checklist che nessuno "
            f"applica. In {dom}, cio' che ha spostato qualcosa e' stato trasformarlo in "
            f"un criterio di esclusione, non in un consiglio. Per te tiene su scala?",
            "Introduce un contro-punto ragionato per generare dibattito, ancorato al "
            "settore dell'utente.",
        ),
    ]

    chosen = templates[:n]
    comments = [
        {"body": body.strip(), "hook_type": hook, "rationale": why}
        for hook, body, why in chosen
    ]

    repost_caption = (
        f"Questo post di {post.author_name} dice una cosa che ripeto spesso ai "
        f"clienti, con parole diverse.\n\n"
        f"La sintesi: {claim.lower()}.\n\n"
        f"Nel mondo {dom} il vero costo non e' fare la cosa giusta, e' rinunciare "
        f"a quelle sbagliate che sembrano opportunita'. Chi ci e' passato sa "
        f"quanto pesa quella scelta.\n\n"
        f"Voi come la vedete?"
    )

    return {
        "prompt_version": PROMPT_VERSION,
        "model": "demo",
        "tokens_input": None,
        "tokens_output": None,
        "output": {
            "skip": False,
            "comments": comments,
            "repost_with_comment": {
                "caption": repost_caption,
                "hook_type": "story",
                "rationale": "Repost con inquadramento personale + invito esplicito al commento.",
            },
        },
    }
