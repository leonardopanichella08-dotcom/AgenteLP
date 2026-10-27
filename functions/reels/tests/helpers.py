"""Verifiche di correttezza dei tagli contro la verità-terreno sintetica."""
from __future__ import annotations


def split_words(truth, segments, tol=0.0):
    """Parole vere spezzate da un taglio: una parola deve stare tutta dentro un segmento o tutta fuori."""
    bad = []
    for w in truth:
        if w.filler and not w.transcribed:
            continue
        inside = [s for s in segments if s[0] - tol <= w.start and w.end <= s[1] + tol]
        touching = [s for s in segments if s[0] < w.end - 0.005 and s[1] > w.start + 0.005]
        if not inside and touching:
            bad.append((w.text, w.start, w.end))
    return bad
