from __future__ import annotations

import re
from collections import Counter

_WORD = re.compile(r"[a-zA-ZàèéìòùÀÈÉÌÒÙ0-9]{3,}")
_STOP = {
    "the", "and", "for", "with", "che", "non", "per", "una", "uno", "del", "della",
    "dei", "delle", "come", "più", "sono", "hai", "questo", "questa", "nel", "nella",
    "con", "gli", "alla", "allo", "dal", "dalla", "your", "you", "are", "this", "that",
}


def _tokens(text: str) -> list[str]:
    return [w.lower() for w in _WORD.findall(text or "") if w.lower() not in _STOP]


def chunk_text(text: str, size: int = 900, overlap: int = 150) -> list[str]:
    """Chunking semplice per paragrafi, poi taglio a lunghezza fissa."""
    text = re.sub(r"\n{3,}", "\n\n", (text or "").strip())
    if not text:
        return []
    paras = [p.strip() for p in text.split("\n\n") if p.strip()]
    chunks: list[str] = []
    buf = ""
    for p in paras:
        if len(buf) + len(p) + 2 <= size:
            buf = f"{buf}\n\n{p}".strip()
        else:
            if buf:
                chunks.append(buf)
            if len(p) <= size:
                buf = p
            else:
                for i in range(0, len(p), size - overlap):
                    chunks.append(p[i : i + size])
                buf = ""
    if buf:
        chunks.append(buf)
    return chunks


class LexicalRetriever:
    """Retriever RAG senza dipendenze: overlap di token pesato (BM25-lite).

    Adeguato per una knowledge base di pochi documenti. Sostituibile con un
    retriever a embedding senza cambiare l'interfaccia `search()`.
    """

    def __init__(self, chunks: list[str]) -> None:
        self.chunks = chunks
        self.tokenised = [_tokens(c) for c in chunks]
        df: Counter[str] = Counter()
        for toks in self.tokenised:
            for t in set(toks):
                df[t] += 1
        self.df = df
        self.n = max(len(chunks), 1)

    def search(self, query: str, k: int = 4) -> list[str]:
        q = _tokens(query)
        if not q or not self.chunks:
            return self.chunks[:k]
        scored: list[tuple[float, int]] = []
        for idx, toks in enumerate(self.tokenised):
            if not toks:
                continue
            tf = Counter(toks)
            score = 0.0
            for term in q:
                if term not in tf:
                    continue
                idf = 1.0 + (self.n / (1 + self.df.get(term, 0)))
                score += (tf[term] / len(toks)) * idf
            if score > 0:
                scored.append((score, idx))
        scored.sort(reverse=True)
        return [self.chunks[i] for _, i in scored[:k]]
