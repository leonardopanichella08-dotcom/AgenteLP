"""Modalità B: scelta dei momenti migliori da un video lungo.

Le finestre candidate sono sequenze di frasi *intere*: l'inizio coincide con
l'inizio di una frase, la fine con la fine di una frase, e i bordi sono
agganciati al silenzio reale. La durata si misura sul montato (dopo jump-cut).
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .audio_analysis import Envelope
from .config import CutPolicy
from .cutting import Gap, Sentence, SegSpec, build_segments
from .textfeat import hook_features
from .transcript import Word

MAX_SENTENCES = 14


@dataclass
class Candidate:
    s_a: int
    s_b: int
    segs: list[SegSpec]
    duration: float
    score: float
    reasons: list[str]
    signals: dict[str, float]
    hook_text: str
    text: str
    meta: dict = field(default_factory=dict)


def edited_duration(segs: list[SegSpec]) -> float:
    return sum(s.end - s.start for s in segs)


def score_window(sents: list[Sentence], lex: list[Word], segs: list[SegSpec], dur: float,
                 min_s: float, max_s: float) -> tuple[float, list[str], dict[str, float]]:
    first, last = sents[0], sents[-1]
    text = " ".join(s.text for s in sents)
    hook = hook_features(first.text, lex[first.a])
    reasons: list[str] = []
    sig: dict[str, float] = {}
    score = 38.0

    def add(name: str, val: float, why: str | None = None) -> None:
        nonlocal score
        sig[name] = round(val, 2)
        score += val
        if why and val > 0:
            reasons.append(why)

    if hook.get("question"):
        add("hook_question", 9, "Si apre con una domanda: curiosità immediata")
    if hook.get("hook_opening"):
        add("hook_opening", 8, "Attacco forte (formula da gancio)")
    if hook.get("numbers") or any(c.isdigit() for c in text):
        add("numbers", 6, "Contiene dati/numeri concreti")
    if hook.get("power_words"):
        add("power_words", 10 * hook["power_words"], "Parole ad alto impatto emotivo")
    if hook.get("exclamation"):
        add("exclamation", 3, "Enfasi e tono deciso")
    if hook.get("bad_start"):
        add("bad_start", -10)
    # integrità dei bordi
    if first.lead_pause >= 0.25:
        add("clean_start", 5, "Attacco pulito: parte dopo una pausa")
    else:
        add("clean_start", -4)
    if last.tail_pause >= 0.35 or last.text.rstrip()[-1:] in ".!?":
        add("clean_end", 5, "Chiude su una frase compiuta")
    else:
        add("clean_end", -8)
    if last.text.rstrip().endswith("?") and len(sents) == 1:
        add("ends_on_question", -4)
    # monologo/dialogo
    if len({s.speaker for s in sents}) == 1:
        add("single_speaker", 3, "Un solo parlante: più facile da seguire e inquadrare")
    # ritmo e durata
    n_words = sum(s.b - s.a + 1 for s in sents)
    wps = n_words / max(dur, 0.1)
    sig["words_per_sec"] = round(wps, 2)
    if 2.0 <= wps <= 3.8:
        add("pace", 6, "Ritmo di parlato ottimale")
    elif wps < 1.5:
        add("pace", -6)
    sweet = 1.0 - abs(dur - 32) / 40
    add("duration_fit", 8 * max(sweet, 0), None)
    # payoff: ultima frase affermativa con parole chiave
    if hook_features(last.text, None).get("power_words"):
        add("payoff", 4, "Si chiude con un payoff forte")
    return max(0.0, min(100.0, score)), reasons, sig


def find_candidates(sents: list[Sentence], lex: list[Word], gaps: list[Gap], env: Envelope, fps: float,
                    policy: CutPolicy, media_duration: float, min_s: float = 15.0, max_s: float = 60.0) -> list[Candidate]:
    cands: list[Candidate] = []
    for i in range(len(sents)):
        for j in range(i, min(len(sents), i + MAX_SENTENCES)):
            win = sents[i:j + 1]
            raw = win[-1].end - win[0].start
            if raw < min_s * 0.8:
                continue
            if raw > max_s * 1.6:
                break
            segs = build_segments(lex, gaps, env, win[0].a, win[-1].b, fps, policy, media_duration=media_duration)
            if not segs:
                continue
            dur = edited_duration(segs)
            if dur < min_s or dur > max_s:
                continue
            score, reasons, sig = score_window(win, lex, segs, dur, min_s, max_s)
            cands.append(Candidate(i, j, segs, dur, score, reasons, sig, win[0].text,
                                   " ".join(s.text for s in win)))
    return cands


def select_top(cands: list[Candidate], k_min: int = 3, k_max: int = 5) -> list[Candidate]:
    """Greedy per punteggio, senza sovrapposizioni di frasi."""
    chosen: list[Candidate] = []
    for c in sorted(cands, key=lambda c: -c.score):
        if all(c.s_b < o.s_a or c.s_a > o.s_b for o in chosen):
            chosen.append(c)
        if len(chosen) >= k_max:
            break
    return chosen
