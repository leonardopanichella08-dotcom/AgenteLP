"""Inviluppo energetico e rilevamento dell'attività vocale.

Serve a una cosa sola: sapere dove c'è davvero voce, perché i timestamp ASR
(Whisper, Deepgram) sbagliano di ~50-150 ms e tagliare "dove dice l'ASR"
mozza le parole.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass
class Envelope:
    hop: float             # secondi tra due campioni di db
    db: np.ndarray         # livello RMS in dB
    active: np.ndarray     # bool: voce presente
    noise_floor: float
    speech_level: float
    threshold: float

    def idx(self, t: float) -> int:
        return int(np.clip(round(t / self.hop), 0, len(self.db) - 1))

    def t(self, i: int) -> float:
        return i * self.hop

    @property
    def duration(self) -> float:
        return len(self.db) * self.hop

    def runs(self, t0: float, t1: float) -> list[tuple[float, float]]:
        """Segmenti attivi (start,end) in [t0,t1], ritagliati alla finestra."""
        i0, i1 = self.idx(max(0.0, t0)), self.idx(min(self.duration, t1))
        seg = self.active[i0:i1 + 1]
        if seg.size == 0:
            return []
        d = np.diff(np.concatenate([[0], seg.astype(np.int8), [0]]))
        starts, ends = np.where(d == 1)[0], np.where(d == -1)[0]
        return [(max(t0, self.t(i0 + s)), min(t1, self.t(i0 + e))) for s, e in zip(starts, ends)]

    def valley(self, t0: float, t1: float, prefer: float | None = None) -> float:
        """Istante di minima energia in [t0,t1] (a parità, il più vicino a `prefer`)."""
        i0, i1 = self.idx(t0), max(self.idx(t0) + 1, self.idx(t1))
        seg = self.db[i0:i1 + 1]
        cost = seg.copy()
        if prefer is not None:
            cost = cost + 0.5 * np.abs((np.arange(len(seg)) + i0) * self.hop - prefer)
        return self.t(i0 + int(np.argmin(cost)))


def compute_envelope(x: np.ndarray, sr: int, hop: float = 0.005, win: float = 0.02,
                     min_active: float = 0.03, close_gap: float = 0.03) -> Envelope:
    n_hop, n_win = max(1, int(sr * hop)), max(1, int(sr * win))
    if len(x) < n_win:
        x = np.pad(x, (0, n_win - len(x)))
    cs = np.concatenate([[0.0], np.cumsum(x.astype(np.float64) ** 2)])
    centers = np.arange(0, len(x), n_hop)
    lo = np.clip(centers - n_win // 2, 0, len(x))
    hi = np.clip(centers + n_win // 2, 0, len(x))
    rms = np.sqrt((cs[hi] - cs[lo]) / np.maximum(hi - lo, 1))
    db = 20 * np.log10(rms + 1e-9)

    noise = float(np.percentile(db, 10))
    speech = float(np.percentile(db, 90))
    # soglia al 25% del range dinamico, mai a meno di 6 dB sopra il rumore
    thr = max(noise + 6.0, noise + 0.25 * (speech - noise))
    active = db > thr
    active = _close_holes(active, int(round(close_gap / hop)))
    active = _drop_blips(active, int(round(min_active / hop)))
    return Envelope(hop=n_hop / sr, db=db, active=active, noise_floor=noise, speech_level=speech, threshold=thr)


def _runs(mask: np.ndarray, value: bool) -> list[tuple[int, int]]:
    m = (mask == value).astype(np.int8)
    d = np.diff(np.concatenate([[0], m, [0]]))
    return list(zip(np.where(d == 1)[0], np.where(d == -1)[0]))


def _close_holes(active: np.ndarray, n: int) -> np.ndarray:
    """Chiude i buchi brevi (occlusive, respiri) dentro il parlato."""
    out = active.copy()
    for s, e in _runs(active, False):
        if 0 < s and e < len(active) and (e - s) < n:
            out[s:e] = True
    return out


def _drop_blips(active: np.ndarray, n: int) -> np.ndarray:
    out = active.copy()
    for s, e in _runs(active, True):
        if (e - s) < n:
            out[s:e] = False
    return out
