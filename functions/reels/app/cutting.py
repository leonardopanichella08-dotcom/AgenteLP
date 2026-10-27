"""Il cuore della precisione dei tagli.

Principio: l'ASR dice *quali* parole ci sono, l'audio dice *dove* finisce
davvero la voce. Ogni punto di taglio viene piazzato nel silenzio reale tra
due attività vocali, mai "dove dice l'ASR", e poi agganciato al frame.

Gap analysis: tra due parole lessicali consecutive guardo le "run" di
attività vocale comprese tra i punti medi delle due parole (il punto medio è
robusto a un jitter ASR fino a mezza parola).
  - >=2 run  -> c'è una pausa vera: off = fine run 1, on = inizio ultima run.
               Le run intermedie sono voce non trascritta (eh, respiri).
  - 1 run    -> parlato continuo: il taglio, se serve, va nella valle di energia.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .audio_analysis import Envelope
from .config import CutPolicy
from .media import frame_round
from .transcript import Word

MIN_SEGMENT = 0.20      # s: segmenti più corti vengono fusi (no flash di 3 frame)
MAX_UNTRANSCRIBED = 1.0  # s: oltre, la "voce non trascritta" potrebbe essere parlato vero
EDGE_SEARCH = 0.6


@dataclass
class Gap:
    i: int                # tra lex[i] e lex[i+1]
    off: float            # fine attività vocale della parola i
    on: float             # inizio attività vocale della parola i+1
    out_t: float          # dove termina il segmento che precede (prima dello snap)
    in_t: float           # dove inizia il segmento che segue (prima dello snap)
    pause: float          # silenzio netto (on-off)
    kind: str             # pause | continuous | none
    removable: bool
    extra_voiced: float = 0.0
    note: str = ""
    out_hi: float = 0.0   # il taglio d'uscita non può superare questo (prossima attività)
    in_lo: float = 0.0    # il taglio d'ingresso non può precedere questo (attività precedente)


@dataclass
class CutInfo:
    asr_time: float       # dove avrebbe tagliato un editor "ingenuo"
    time: float           # taglio finale, agganciato al frame
    frame: int
    method: str           # silence_gap | valley | file_edge
    silence: tuple[float, float] | None
    confidence: float
    reason: str

    def to_dict(self) -> dict:
        return {"asr_time": round(self.asr_time, 6), "time": round(self.time, 6), "frame": self.frame,
                "method": self.method,
                "silence": [round(self.silence[0], 6), round(self.silence[1], 6)] if self.silence else None,
                "confidence": round(self.confidence, 2), "reason": self.reason}


@dataclass
class SegSpec:
    start: float
    end: float
    cut_in: CutInfo
    cut_out: CutInfo
    first_word: int       # indici in lex, inclusi
    last_word: int
    removed_before: str | None = None  # pause | filler | drop | None
    warnings: list[str] = field(default_factory=list)


def _active_near(env: Envelope, t: float, direction: int, maxdist: float) -> float:
    """Se `t` non è su voce, sposta fino alla voce più vicina nella direzione data."""
    i = env.idx(t)
    if env.active[i]:
        return t
    step = direction
    for k in range(1, int(maxdist / env.hop) + 1):
        j = i + step * k
        if 0 <= j < len(env.active) and env.active[j]:
            return env.t(j)
    return t


def analyze_gaps(lex: list[Word], env: Envelope, policy: CutPolicy) -> list[Gap]:
    gaps: list[Gap] = []
    for i in range(len(lex) - 1):
        w, n = lex[i], lex[i + 1]
        lo = _active_near(env, w.mid, -1, 0.25)
        hi = _active_near(env, max(n.mid, lo + env.hop), +1, 0.25)
        runs = env.runs(lo, hi)
        if len(runs) >= 2:
            off, on = runs[0][1], runs[-1][0]
            pause = on - off
            extra = sum(e - s for s, e in runs[1:-1])
            out_hi = runs[1][0] - 0.005     # prossima attività (anche voce non trascritta)
            in_lo = runs[-2][1] + 0.005
            out_t = off + min(policy.tail_pad, max(out_hi - off, 0) / 2)
            in_t = on - min(policy.lead_pad, max(on - in_lo, 0) / 2)
            removable = pause >= policy.max_gap and (in_t - out_t) >= policy.min_removal
            note = ""
            if removable and extra >= MAX_UNTRANSCRIBED:
                removable, note = False, "long_untranscribed_voice"
            gaps.append(Gap(i, off, on, out_t, in_t, pause, "pause", removable, extra, note, out_hi, in_lo))
        else:
            v = env.valley(lo, hi, prefer=(w.end + n.start) / 2)
            gaps.append(Gap(i, v, v, v, v, 0.0, "continuous", False, 0.0, "", v, v))
    return gaps


def _edge_in(env: Envelope, w: Word, policy: CutPolicy) -> tuple[float, tuple[float, float] | None]:
    lo = max(0.0, w.start - EDGE_SEARCH)
    hi = _active_near(env, w.mid, -1, 0.25)
    runs = env.runs(lo, hi)
    if not runs:
        return max(0.0, w.start - policy.lead_pad), None
    on = runs[-1][0]
    prev_end = runs[-2][1] if len(runs) > 1 else lo
    pause = on - prev_end
    return on - min(policy.lead_pad, max(pause, 0) / 2), (prev_end, on)


def _edge_out(env: Envelope, w: Word, policy: CutPolicy, dur: float) -> tuple[float, tuple[float, float] | None]:
    hi = min(dur, w.end + EDGE_SEARCH)
    lo = _active_near(env, w.mid, -1, 0.25)
    runs = env.runs(lo, hi)
    if not runs:
        return min(dur, w.end + policy.tail_pad), None
    off = runs[0][1]
    next_on = runs[1][0] if len(runs) > 1 else hi
    pause = next_on - off
    return off + min(policy.tail_pad, max(pause, 0) / 2), (off, next_on)


def _snap(t: float, lo: float, hi: float, fps: float) -> tuple[float, bool]:
    """Frame boundary più vicino a t che cada dentro [lo, hi] (ok=False se non esiste)."""
    import math
    hi = max(hi, lo)
    c = round(t * fps)
    k_lo, k_hi = math.ceil(lo * fps - 1e-6), math.floor(hi * fps + 1e-6)
    if k_lo <= k_hi:
        return min(max(c, k_lo), k_hi) / fps, True
    return c / fps, False  # intervallo più corto di un frame


def _cutinfo(asr_t: float, t: float, ok: bool, fps: float, gap: Gap | None,
             sil: tuple[float, float] | None, kind: str, reason: str) -> CutInfo:
    if gap is not None and gap.kind == "pause":
        method = "silence_gap"
        conf = 1.0 if gap.pause >= 0.12 else 0.7
        sil = (gap.off, gap.on)
    elif sil is not None:
        method, conf = "file_edge", 0.9
    else:
        method, conf = ("valley", 0.4) if gap is not None else ("file_edge", 0.6)
    if not ok:
        conf = min(conf, 0.3)
    return CutInfo(asr_t, t, round(t * fps), method, sil, conf, reason)


def build_segments(lex: list[Word], gaps: list[Gap], env: Envelope, a: int, b: int, fps: float,
                   policy: CutPolicy, drop: frozenset[int] = frozenset(),
                   media_duration: float | None = None) -> list[SegSpec]:
    """Segmenti da tenere per le parole lex[a..b] (incluse).

    `drop`: indici lex da eliminare comunque (false partenze, ripetizioni).
    Le pause lunghe e la voce non trascritta tra due parole tenute vengono tolte
    secondo `policy`. Tutti i punti sono dentro silenzi e agganciati ai frame.
    """
    dur = media_duration if media_duration is not None else env.duration
    kept = [k for k in range(a, b + 1) if k not in drop]
    if not kept:
        return []

    # ── bordi (a monte/valle del primo/ultimo tenuto)
    first, last = kept[0], kept[-1]
    if first > 0:
        g = gaps[first - 1]
        in_raw, in_gap, in_sil = g.in_t, g, None
        lo, hi = g.in_lo, g.on
    else:
        in_raw, in_sil = _edge_in(env, lex[first], policy)
        in_gap = None
        lo, hi = (in_sil[0] + 0.005, in_sil[1]) if in_sil else (0.0, lex[first].start)
    t_in, ok_in = _snap(in_raw, lo, max(hi, lo), fps)
    first_in = _cutinfo(lex[first].start, t_in, ok_in, fps, in_gap, in_sil, "edge_in", "inizio reel")

    if last < len(lex) - 1:
        g = gaps[last]
        out_raw, out_gap, out_sil = g.out_t, g, None
        lo, hi = g.off, g.out_hi
    else:
        out_raw, out_sil = _edge_out(env, lex[last], policy, dur)
        out_gap = None
        lo, hi = (out_sil[0], out_sil[1] - 0.005) if out_sil else (lex[last].mid, dur)
        hi = min(hi, dur)
    t_out, ok_out = _snap(out_raw, lo, max(hi, lo), fps)
    last_out = _cutinfo(lex[last].end, t_out, ok_out, fps, out_gap, out_sil, "edge_out", "fine reel")

    # ── tagli interni
    pieces: list[list] = []   # [first_idx, last_idx, in_cutinfo, out_cutinfo, removed_before, warnings]
    cur_first, cur_in, removed = first, first_in, None
    pending: list[str] = []
    for p, q in zip(kept, kept[1:]):
        forced = q > p + 1
        g_out, g_in = gaps[p], gaps[q - 1]
        if forced:
            do_cut = (g_in.in_t - g_out.out_t) >= 0.04 and g_out.kind == "pause" and g_in.kind == "pause"
            reason = "drop"
        else:
            do_cut = g_out.removable
            reason = "pause"
        if not do_cut:
            if forced:
                pending.append(f"parole '{' '.join(w.text for w in lex[p + 1:q])}' non separabili dal parlato (nessun silenzio): mantenute")
            continue
        o_t, o_ok = _snap(g_out.out_t, g_out.off, g_out.out_hi, fps)
        i_t, i_ok = _snap(g_in.in_t, g_in.in_lo, g_in.on, fps)
        if i_t <= o_t:
            continue
        pieces.append([cur_first, p, cur_in,
                       _cutinfo(lex[p].end, o_t, o_ok, fps, g_out, None, "cut_out", reason), removed, pending])
        pending = []
        cur_first, removed = q, reason
        cur_in = _cutinfo(lex[q].start, i_t, i_ok, fps, g_in, None, "cut_in", reason)
    pieces.append([cur_first, last, cur_in, last_out, removed, pending])

    # ── niente segmenti minuscoli: fondi col precedente
    merged: list[list] = []
    for pc in pieces:
        seg_len = (pc[3].time - pc[2].time)
        if merged and seg_len < MIN_SEGMENT:
            prev = merged[-1]
            prev[1], prev[3] = pc[1], pc[3]
            prev[5].append("segmento troppo corto fuso col precedente")
        else:
            merged.append(pc)

    return [SegSpec(start=pc[2].time, end=pc[3].time, cut_in=pc[2], cut_out=pc[3],
                    first_word=pc[0], last_word=pc[1], removed_before=pc[4], warnings=pc[5])
            for pc in merged if pc[3].time > pc[2].time]


# ── frasi ─────────────────────────────────────────────────────────────────

@dataclass
class Sentence:
    id: int
    a: int
    b: int
    start: float
    end: float
    text: str
    speaker: str | None
    lead_pause: float     # silenzio netto prima della frase (pulizia del punto di ingresso)
    tail_pause: float     # silenzio netto dopo la frase


def split_sentences(lex: list[Word], gaps: list[Gap], sentence_gap: float = 0.7, max_words: int = 45) -> list[Sentence]:
    if not lex:
        return []
    bounds: list[int] = []   # indice dell'ultima parola di ogni frase
    run_start = 0
    for i in range(len(lex) - 1):
        w, n = lex[i], lex[i + 1]
        end_punct = w.text.rstrip()[-1:] in ".!?…"
        long_gap = gaps[i].pause >= sentence_gap
        spk = w.speaker is not None and n.speaker is not None and w.speaker != n.speaker
        too_long = (i - run_start + 1) >= max_words and gaps[i].pause >= 0.25
        if end_punct or long_gap or spk or too_long:
            bounds.append(i)
            run_start = i + 1
    bounds.append(len(lex) - 1)

    sents: list[Sentence] = []
    a = 0
    for b in bounds:
        if b < a:
            continue
        sents.append(Sentence(
            id=len(sents), a=a, b=b, start=lex[a].start, end=lex[b].end,
            text=" ".join(w.text for w in lex[a:b + 1]),
            speaker=lex[a].speaker,
            lead_pause=gaps[a - 1].pause if a > 0 else 1.0,
            tail_pause=gaps[b].pause if b < len(gaps) else 1.0,
        ))
        a = b + 1
    # frasi di una sola parola ("Esatto.") si fondono col seguito
    out: list[Sentence] = []
    for s in sents:
        if out and (out[-1].b - out[-1].a + 1) < 2 and out[-1].speaker == s.speaker:
            p = out.pop()
            s = Sentence(p.id, p.a, s.b, p.start, s.end, p.text + " " + s.text, p.speaker, p.lead_pause, s.tail_pause)
        out.append(s)
    for k, s in enumerate(out):
        s.id = k
    return out
