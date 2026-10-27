"""B-roll di stock: pianificazione delle finestre + client Pexels (Shutterstock: stessa interfaccia)."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Protocol

import httpx

from .schemas import Broll, Reel
from .textfeat import STOP

MIN_SEG_FOR_BROLL = 3.5   # s: segmenti più corti restano sul parlante
LEAD_KEEP = 1.2           # s: i primi istanti del segmento restano sul parlante (aggancio visivo)
TAIL_KEEP = 1.0
SPACING = 6.0             # s tra due b-roll
LENGTH = 1.8


class BrollProvider(Protocol):
    def fetch(self, query: str, dest: Path) -> Path | None: ...


class PexelsClient:
    name = "pexels"

    def __init__(self, key: str, client: httpx.Client | None = None, orientation: str = "portrait"):
        self.key, self.orientation = key, orientation
        self.http = client or httpx.Client(timeout=60, follow_redirects=True)

    @classmethod
    def from_env(cls) -> "PexelsClient | None":
        k = os.environ.get("PEXELS_API_KEY")
        return cls(k) if k else None

    def fetch(self, query: str, dest: Path) -> Path | None:
        r = self.http.get("https://api.pexels.com/videos/search", headers={"Authorization": self.key},
                          params={"query": query, "orientation": self.orientation, "per_page": 5, "size": "medium"})
        r.raise_for_status()
        for v in r.json().get("videos", []):
            files = [f for f in v.get("video_files", []) if f.get("file_type") == "video/mp4" and (f.get("width") or 0) >= 540]
            if not files:
                continue
            best = min(files, key=lambda f: abs((f.get("width") or 0) - 1080))      # vicino a 1080, senza esagerare
            dest.parent.mkdir(parents=True, exist_ok=True)
            out = dest / f"pexels_{v['id']}.mp4"
            if not out.exists():
                with self.http.stream("GET", best["link"]) as resp:
                    resp.raise_for_status()
                    with open(out, "wb") as f:
                        for chunk in resp.iter_bytes():
                            f.write(chunk)
            return out
        return None


def plan_windows(reel: Reel, queries: list[str] | None = None, max_n: int = 3) -> list[Broll]:
    """Finestre di b-roll dentro segmenti lunghi, ancorate a una parola-chiave se c'è."""
    out: list[Broll] = []
    last_end = -SPACING
    qi = 0
    for seg in reel.timeline:
        d = seg.out_end - seg.out_start
        if d < MIN_SEG_FOR_BROLL or len(out) >= max_n:
            continue
        kws = [w for w in reel.words if w.segment_id == seg.id and w.emphasis != "none"
               and seg.out_start + LEAD_KEEP <= w.out_start <= seg.out_end - TAIL_KEEP - 0.5]
        if kws:
            start = max(kws[0].out_start - 0.2, seg.out_start + LEAD_KEEP)
            query = kws[0].text.strip(".,!?;:").lower()
        else:
            start = seg.out_start + LEAD_KEEP
            query = None
        if queries:
            query = queries[qi % len(queries)]; qi += 1
        if not query or query in STOP or start - last_end < SPACING:
            continue
        end = min(start + LENGTH, seg.out_end - TAIL_KEEP)
        if end - start < 1.0:
            continue
        out.append(Broll(out_start=round(start, 3), out_end=round(end, 3), query=query, provider="pexels"))
        last_end = end
    return out


def resolve(reel: Reel, provider: BrollProvider, dest: Path) -> list[str]:
    """Scarica gli asset; le finestre senza risultato vengono tolte. Ritorna gli avvisi."""
    warns, ok = [], []
    for b in reel.broll:
        try:
            p = provider.fetch(b.query, dest)
        except Exception as e:
            warns.append(f"b-roll '{b.query}': {e}")
            continue
        if p is None:
            warns.append(f"b-roll '{b.query}': nessun risultato")
            continue
        b.asset_path = str(p)
        ok.append(b)
    reel.broll = ok
    return warns
