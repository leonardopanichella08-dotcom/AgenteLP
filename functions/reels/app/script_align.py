"""Modalità A: allineamento script ↔ trascritto delle clip e scelta della take migliore.

Allineamento semi-globale (Needleman-Wunsch con inizio/fine liberi sulla clip):
per ogni unità dello script trovo *tutti* i punti della clip dove viene
pronunciata (più take nella stessa clip = più candidati), poi scelgo la
migliore per completezza, assenza di esitazioni e (a parità) la più recente.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from difflib import SequenceMatcher

import numpy as np

from .transcript import Word, normalize

INS_COST = 0.7     # parola in più nella clip (esitazione, falsa partenza)
DEL_COST = 1.0     # parola dello script non pronunciata
MAX_COST_RATIO = 0.45


def split_script(text: str, max_words: int = 30) -> list[str]:
    """Una unità per riga; righe lunghe vengono divise per frase."""
    units: list[str] = []
    for line in [l.strip() for l in text.splitlines() if l.strip()]:
        if len(line.split()) <= max_words:
            units.append(line)
        else:
            units += [p.strip() for p in re.split(r"(?<=[.!?…])\s+", line) if p.strip()]
    return units


def tokens(text: str) -> list[str]:
    return [t for t in (normalize(w) for w in text.split()) if t]


def _sub(a: str, b: str) -> float:
    if a == b:
        return 0.0
    r = SequenceMatcher(None, a, b).ratio()
    return 1.0 - r if r >= 0.75 else 1.0


@dataclass
class Take:
    take_id: str
    source_id: str
    a: int                  # indici in lex (inclusi)
    b: int
    cost: float
    similarity: float
    score: float
    drop: frozenset[int] = frozenset()
    n_inserted: int = 0
    long_pauses: int = 0
    order: float = 0.0
    note: list[str] = field(default_factory=list)


def _align(S: list[str], C: list[str]) -> tuple[np.ndarray, np.ndarray]:
    m, n = len(S), len(C)
    D = np.zeros((m + 1, n + 1))
    D[1:, 0] = np.arange(1, m + 1) * DEL_COST
    B = np.zeros((m + 1, n + 1), dtype=np.int8)   # 0 match/sub, 1 del(script), 2 ins(clip)
    for i in range(1, m + 1):
        for j in range(1, n + 1):
            c_match = D[i - 1, j - 1] + _sub(S[i - 1], C[j - 1])
            c_del = D[i - 1, j] + DEL_COST
            c_ins = D[i, j - 1] + INS_COST
            best = min(c_match, c_del, c_ins)
            D[i, j] = best
            B[i, j] = 0 if best == c_match else (1 if best == c_del else 2)
    return D, B


def find_takes(script_tokens: list[str], lex: list[Word], source_id: str, clip_order: int = 0) -> list[Take]:
    m = len(script_tokens)
    C = [w.norm for w in lex]
    if m == 0 or not C:
        return []
    D, B = _align(script_tokens, C)
    last = D[m]
    cands = []
    for j in range(1, len(C) + 1):
        left = last[j - 1] if j > 1 else np.inf
        right = last[j + 1] if j < len(C) else np.inf
        if last[j] <= left and last[j] <= right and last[j] / m <= MAX_COST_RATIO:
            cands.append(j)
    takes: list[Take] = []
    for j_end in cands:
        i, j = m, j_end
        inserted: list[int] = []
        while i > 0:
            if j == 0:
                i -= 1
                continue
            op = B[i, j]
            if op == 0:
                i -= 1; j -= 1
            elif op == 1:
                i -= 1
            else:
                inserted.append(j - 1); j -= 1
        a, b = j, j_end - 1           # a = primo indice clip consumato
        # j può indicare un inizio su un inserimento iniziale: salta fino alla prima parola abbinata
        inserted = [k for k in inserted if a <= k <= b]
        while inserted and a in inserted:
            inserted.remove(a); a += 1
        cost = float(last[j_end])
        sim = max(0.0, 1.0 - cost / m)
        long_p = sum(1 for k in range(a, b) if lex[k + 1].start - lex[k].end > 0.7)
        score = sim - 0.04 * len(inserted) - 0.05 * long_p
        takes.append(Take(f"{source_id}@{lex[a].start:.2f}", source_id, a, b, cost, sim, score,
                          frozenset(inserted), len(inserted), long_p,
                          order=clip_order * 10000 + lex[a].start))
    # deduplica sovrapposti: tieni il migliore
    takes.sort(key=lambda t: -t.score)
    kept: list[Take] = []
    for t in takes:
        if all(t.b < k.a or t.a > k.b for k in kept):
            kept.append(t)
    return sorted(kept, key=lambda t: t.order)


def choose_takes(units: list[str], lex_by_source: dict[str, list[Word]]) -> list[dict]:
    """Per ogni unità: take scelta + alternative. Una take non viene riusata da due unità."""
    used: dict[str, list[tuple[int, int]]] = {s: [] for s in lex_by_source}
    out = []
    for u, text in enumerate(units):
        toks = tokens(text)
        cands: list[Take] = []
        for k, (sid, lex) in enumerate(lex_by_source.items()):
            for t in find_takes(toks, lex, sid, k):
                if all(t.b < a or t.a > b for a, b in used[sid]):
                    cands.append(t)
        # a parità (±0.03) vince la take più recente
        cands.sort(key=lambda t: (-round(t.score / 0.03), -t.order))
        chosen = cands[0] if cands and cands[0].similarity >= 0.6 else None
        if chosen:
            used[chosen.source_id].append((chosen.a, chosen.b))
        status = "missing" if chosen is None else ("matched" if chosen.similarity >= 0.85 else "weak")
        out.append({"unit": u, "text": text, "chosen": chosen, "status": status, "candidates": cands})
    return out
