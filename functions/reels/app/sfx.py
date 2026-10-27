"""SFX sintetizzati (numpy) → nessun asset esterno da licenziare. Sostituibili con una libreria reale."""
from __future__ import annotations

import wave
from pathlib import Path

import numpy as np

SR = 48000


def _fade(x: np.ndarray, a: float = 0.003, r: float = 0.01) -> np.ndarray:
    na, nr = int(a * SR), int(r * SR)
    x = x.copy()
    x[:na] *= np.linspace(0, 1, na); x[-nr:] *= np.linspace(1, 0, nr)
    return x


def whoosh(dur: float = 0.45) -> np.ndarray:
    rng = np.random.default_rng(1)
    n = int(dur * SR); t = np.linspace(0, 1, n)
    noise = rng.standard_normal(n)
    # sweep passa-banda: media mobile con finestra che si stringe
    out = np.zeros(n)
    for k, w in enumerate([48, 24, 12, 6]):
        out += np.convolve(noise, np.ones(w) / w, mode="same") * (1.0 - 0.2 * k)
    env = np.sin(np.pi * t) ** 2 * (1 - 0.3 * t)
    return _fade(out * env / (np.abs(out * env).max() + 1e-9) * 0.8)


def pop(dur: float = 0.12) -> np.ndarray:
    n = int(dur * SR); t = np.arange(n) / SR
    f = 700 * np.exp(-t * 28) + 180
    ph = 2 * np.pi * np.cumsum(f) / SR
    return _fade(np.sin(ph) * np.exp(-t * 32) * 0.9, 0.001, 0.02)


def ding(dur: float = 0.9) -> np.ndarray:
    n = int(dur * SR); t = np.arange(n) / SR
    s = sum(a * np.sin(2 * np.pi * f * t) * np.exp(-t * d)
            for f, a, d in [(1318.5, 1.0, 5.0), (2637.0, 0.35, 7.0), (3951.0, 0.15, 9.0)])
    return _fade(s / np.abs(s).max() * 0.7)


def click(dur: float = 0.05) -> np.ndarray:
    rng = np.random.default_rng(2)
    n = int(dur * SR); t = np.arange(n) / SR
    return _fade(rng.standard_normal(n) * np.exp(-t * 140) * 0.8, 0.0005, 0.01)


def riser(dur: float = 1.2) -> np.ndarray:
    n = int(dur * SR); t = np.linspace(0, 1, n)
    f = 200 + 1800 * t ** 2
    return _fade(np.sin(2 * np.pi * np.cumsum(f) / SR) * t ** 1.5 * 0.6, 0.01, 0.03)


GEN = {"whoosh": whoosh, "pop": pop, "ding": ding, "click": click, "riser": riser}


def ensure_sfx(cache: Path) -> dict[str, Path]:
    cache.mkdir(parents=True, exist_ok=True)
    out = {}
    for name, fn in GEN.items():
        p = cache / f"{name}.wav"
        if not p.exists():
            pcm = (np.clip(fn(), -1, 1) * 32767).astype(np.int16)
            with wave.open(str(p), "wb") as f:
                f.setnchannels(1); f.setsampwidth(2); f.setframerate(SR); f.writeframes(pcm.tobytes())
        out[name] = p
    return out
