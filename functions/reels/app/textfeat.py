"""Feature testuali offline: keyword, enfasi, emoji, ganci, caption/hashtag."""
from __future__ import annotations

import re
from collections import Counter

from .transcript import Word, normalize

STOP = set("""a ad al alla alle allo agli ai anche che chi ci come con cosa così cui da dal dalla dei del della delle dello di dove e ed
è era ero essere fa fare fatto gli ha hanno ho i il in io la le lei lo loro lui ma mai me mi molto ne nei nel nella no noi non nostro o per
perché più poi può quando quel quella quello questa queste questi questo qui quindi se sei sembra si sia siamo sono su sua sue sui sul sulla
suo tra tu tuo tutti tutto un una uno vi voi vostro the and for you your that this with are was have not but what from they will""".split())

POWER = set("""segreto segreti errore errori mai sempre nessuno tutti gratis davvero incredibile pazzesco fondamentale problema soldi
vincere vincente perdere paura verità bugia pericolo attenzione stop smetti smettere ricorda subito oggi ora quarantamila milione
milioni miliardi record unico esclusivo facile semplice difficile impossibile velocemente ritenzione viral virale fallimento successo
secret mistake never always nobody free truth money win lose fear warning stop""".split())

NUMBER_WORDS = set("""uno due tre quattro cinque sei sette otto nove dieci venti trenta quaranta cinquanta sessanta settanta ottanta
novanta cento mille milione miliardo primo secondo terzo""".split())

EMOJI = {
    "soldi": "💰", "money": "💰", "segreto": "🤫", "secret": "🤫", "errore": "❌", "mistake": "❌", "attenzione": "⚠️",
    "idea": "💡", "successo": "🚀", "tempo": "⏱️", "video": "🎬", "montaggio": "✂️", "cervello": "🧠", "amore": "❤️",
    "vincere": "🏆", "fuoco": "🔥", "ritmo": "🎵", "audio": "🎧", "onda": "🌊", "pausa": "⏸️", "pause": "⏸️",
    "paura": "😱", "verità": "✅", "gratis": "🎁", "domanda": "❓", "fantastico": "🤩", "grazie": "🙏",
}

HOOK_START = re.compile(r"^(come|perch[eé]|il segreto|nessuno|smetti|ecco|attenzione|ti|vi|hai mai|sai|se |quando|mai|davvero|\d)", re.I)
CONTINUATION = {"e", "ma", "quindi", "allora", "infatti", "cioè", "poi", "anche", "perciò", "dunque", "però", "invece", "and", "but", "so"}


def is_number(w: Word) -> bool:
    n = w.norm
    return bool(re.search(r"\d", w.text)) or n in NUMBER_WORDS


def keyword_scores(words: list[Word]) -> dict[int, float]:
    """Punteggio d'enfasi per indice parola (solo candidati > 0)."""
    freq = Counter(w.norm for w in words if w.norm not in STOP and len(w.norm) > 3)
    out: dict[int, float] = {}
    for i, w in enumerate(words):
        n = w.norm
        if not n or n in STOP:
            continue
        s = 0.0
        if is_number(w):
            s += 2.0
        if n in POWER:
            s += 2.0
        if w.text.endswith("!"):
            s += 0.5
        if len(n) >= 7:
            s += 0.6
        if n in EMOJI:
            s += 0.6
        s += 0.4 / max(1, freq.get(n, 1))
        if s >= 1.2:
            out[i] = s
    return out


def pick_emphasis(words: list[Word], max_gap_words: int = 5) -> dict[int, tuple[str, str | None]]:
    """indice -> (categoria, emoji). Al massimo una enfasi ogni `max_gap_words` parole."""
    scores = keyword_scores(words)
    chosen: dict[int, tuple[str, str | None]] = {}
    last = -999
    for i in sorted(scores, key=lambda k: -scores[k]):
        if all(abs(i - j) >= max_gap_words for j in chosen):
            w = words[i]
            cat = "number" if is_number(w) else ("power" if w.norm in POWER else "keyword")
            chosen[i] = (cat, EMOJI.get(w.norm))
    return chosen


def top_keywords(words: list[Word], n: int = 6) -> list[str]:
    c = Counter(w.norm for w in words if w.norm not in STOP and len(w.norm) > 4 and not re.search(r"\d", w.norm))
    return [k for k, _ in c.most_common(n)]


def hook_features(text: str, first_word: Word | None) -> dict[str, float]:
    t = text.strip()
    f: dict[str, float] = {}
    if "?" in t[:120]:
        f["question"] = 1.0
    if HOOK_START.search(t):
        f["hook_opening"] = 1.0
    if re.search(r"\d", t):
        f["numbers"] = 1.0
    pw = sum(1 for w in t.split() if normalize(w) in POWER)
    if pw:
        f["power_words"] = min(1.0, pw / 3)
    if "!" in t:
        f["exclamation"] = 1.0
    if first_word is not None and first_word.norm in CONTINUATION:
        f["bad_start"] = 1.0
    return f


def make_social(title_src: str, keywords: list[str], hook: str) -> dict:
    title = (hook or title_src).strip().rstrip(".!?…")
    title = (title[:70].rsplit(" ", 1)[0] + "…") if len(title) > 72 else title
    tags = [f"#{k}" for k in keywords[:4]] + ["#reels", "#shorts", "#perte"]
    caption = f"{title}.\n\n{title_src.strip()[:180]}{'…' if len(title_src) > 180 else ''}\n\nSalva e condividi 👇"
    return {"title": title, "caption": caption, "hashtags": list(dict.fromkeys(tags))[:8]}
