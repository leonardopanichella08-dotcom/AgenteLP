from __future__ import annotations

from dataclasses import dataclass, field
from textwrap import dedent

PROMPT_VERSION = "luka-sys-2026-02"


@dataclass
class BrandContext:
    display_name: str
    account_type: str  # "personal" | "company"
    headline: str | None = None
    industry: str | None = None
    mission: str = ""
    value_proposition: str = ""
    icp: str = ""
    market_context: str = ""
    tone_of_voice: str = "autorevole, diretto, concreto, zero buzzword"
    language: str = "it"
    banned_phrases: list[str] = field(default_factory=list)
    goal: str = "Generare conversazione e traffico qualificato verso il profilo dell'utente"


@dataclass
class DiscoveredPost:
    author_name: str
    niche: str
    url: str
    text: str
    author_headline: str | None = None
    reactions: int = 0
    comments: int = 0
    views: int | None = None
    engagement_score: float = 0.0


# Blocco identità: stabile tra utenti => cache-abile via prompt caching.
LUKA_IDENTITY = dedent(
    """
    Sei LUKA, ghostwriter e stratega di personal branding su LinkedIn.
    Scrivi commenti e repost per conto di un professionista o di un'azienda.
    Il tuo output verra' pubblicato manualmente dall'utente: deve essere
    pronto all'uso, senza segnaposto e senza meta-commenti.

    OBIETTIVO
    Generare conversazione, visibilita' e traffico qualificato verso il
    profilo dell'utente. NON fai autopromozione esplicita: attiri
    l'attenzione con valore, non con un pitch.

    REGOLE DI TONO (vincolanti)
    - Prima persona, lingua dell'utente, registro naturale e parlato.
    - Frasi brevi. Nessun gergo corporate, nessun "in un mondo sempre piu'...".
    - Vietato: "Great post!", "Totally agree", "Grazie per la condivisione",
      complimenti generici, riassunti del post altrui.
    - Niente hashtag e niente elenchi puntati dentro i commenti.
    - Massimo 1 emoji, solo se aggiunge significato.
    - Mai rivelare di essere un'AI. Mai inventare dati sull'autore del post.

    PRINCIPI DI VIRALITA' (applicane almeno 3 per risposta)
    1. Aggiungi una prospettiva nuova o un contro-punto ragionato, non un "si'".
    2. Porta UN elemento concreto (dato, esempio, micro-storia) coerente col
       contesto dell'utente, in modo implicito, mai come pubblicita'.
    3. Chiudi con una domanda aperta che spinge l'autore o altri a rispondere.
    4. Prima riga = hook che regge anche se troncato nel feed (~120 caratteri).
    5. Commento: 300-600 caratteri. Caption di repost: 400-800 caratteri.

    SICUREZZA
    - Nessuna affermazione non supportabile. Niente politica, religione,
      attacchi personali. Rispetta la lista di frasi vietate dell'utente.
    - Se il post e' fuori nicchia, tossico o non offre un aggancio onesto,
      imposta skip = true con un motivo.
    """
).strip()


def build_system_blocks(ctx: BrandContext, rag_snippets: list[str] | None = None) -> list[dict]:
    kb = "\n".join(f"- {s.strip()}" for s in (rag_snippets or []) if s.strip())
    kb = kb or "Nessun documento aggiuntivo."
    banned = ", ".join(ctx.banned_phrases) or "(nessuna)"

    context_block = dedent(
        f"""
        CONTESTO DELL'UTENTE
        Nome:             {ctx.display_name}  ({ctx.account_type})
        Headline:         {ctx.headline or "-"}
        Mission:          {ctx.mission or "-"}
        Value prop:       {ctx.value_proposition or "-"}
        ICP (target):     {ctx.icp or "-"}
        Contesto mercato: {ctx.market_context or "-"}
        Tone of voice:    {ctx.tone_of_voice}
        Obiettivo:        {ctx.goal}
        Frasi vietate:    {banned}
        Lingua output:    {ctx.language}

        KNOWLEDGE BASE (usa solo se pertinente, senza citarla esplicitamente)
        {kb}
        """
    ).strip()

    return [
        {"type": "text", "text": LUKA_IDENTITY, "cache_control": {"type": "ephemeral"}},
        {"type": "text", "text": context_block},
    ]


def build_user_message(post: DiscoveredPost, n_comment_variants: int) -> str:
    return (
        "POST VIRALE DA ANALIZZARE\n"
        f"Autore:     {post.author_name} - {post.author_headline or '-'}\n"
        f"Nicchia:    {post.niche}\n"
        f"Engagement: {post.reactions} reaction, {post.comments} commenti, "
        f"{post.views if post.views is not None else 'n/d'} views "
        f"(score {post.engagement_score:.2f})\n"
        f"URL:        {post.url}\n"
        "--- TESTO DEL POST ---\n"
        f"{post.text.strip()}\n"
        "--- FINE TESTO ---\n\n"
        f"Genera {n_comment_variants} varianti di commento indipendenti + 1 caption "
        "di repost. Chiama lo strumento submit_engagement."
    )


SUBMIT_TOOL = {
    "name": "submit_engagement",
    "description": "Restituisce le proposte di engagement per il post analizzato.",
    "input_schema": {
        "type": "object",
        "properties": {
            "skip": {"type": "boolean"},
            "skip_reason": {"type": "string"},
            "comments": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "body": {"type": "string"},
                        "hook_type": {
                            "type": "string",
                            "enum": ["contrarian", "data_point", "story", "question", "reframe"],
                        },
                        "rationale": {"type": "string"},
                    },
                    "required": ["body", "hook_type", "rationale"],
                },
            },
            "repost_with_comment": {
                "type": "object",
                "properties": {
                    "caption": {"type": "string"},
                    "hook_type": {
                        "type": "string",
                        "enum": ["contrarian", "data_point", "story", "question", "reframe"],
                    },
                    "rationale": {"type": "string"},
                },
                "required": ["caption", "hook_type", "rationale"],
            },
        },
        "required": ["skip", "comments"],
    },
}
