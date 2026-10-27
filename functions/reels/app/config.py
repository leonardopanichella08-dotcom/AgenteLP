"""Formati di export, piattaforme e policy di taglio (tutto in un posto)."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

DATA_DIR = Path(os.environ.get("REELS_DATA_DIR", Path(__file__).resolve().parent.parent / "data"))
LLM_MODEL = os.environ.get("REELS_LLM_MODEL", "claude-sonnet-5-5")


@dataclass(frozen=True)
class FormatSpec:
    id: str
    width: int
    height: int
    platforms: tuple[str, ...]
    # zone sicure (frazione dell'altezza) occupate dalla UI della piattaforma
    safe_top: float
    safe_bottom: float
    sub_y: float  # posizione verticale dei sottotitoli (0=alto, 1=basso), centro riga

    @property
    def aspect(self) -> float:
        return self.width / self.height


FORMATS: dict[str, FormatSpec] = {
    f.id: f
    for f in [
        FormatSpec("9:16", 1080, 1920,
                   ("tiktok", "instagram_reels", "youtube_shorts", "facebook_reels"),
                   safe_top=0.10, safe_bottom=0.22, sub_y=0.66),
        FormatSpec("4:5", 1080, 1350, ("instagram_feed", "facebook_feed"),
                   safe_top=0.04, safe_bottom=0.10, sub_y=0.72),
        FormatSpec("1:1", 1080, 1080, ("linkedin_feed", "instagram_grid", "facebook_feed_square"),
                   safe_top=0.04, safe_bottom=0.08, sub_y=0.74),
        FormatSpec("16:9", 1920, 1080, ("linkedin_video", "youtube", "web"),
                   safe_top=0.04, safe_bottom=0.08, sub_y=0.82),
    ]
}


@dataclass(frozen=True)
class CutPolicy:
    """Quanto aggressivo è il jump-cut. Tutti i valori in secondi."""
    name: str
    max_gap: float      # pausa (tra attività vocale) oltre cui si taglia
    tail_pad: float     # silenzio lasciato dopo la parola che precede il taglio
    lead_pad: float     # silenzio lasciato prima della parola che segue il taglio
    min_removal: float  # non tagliare se rimuoveresti meno di così


POLICIES = {
    "tight": CutPolicy("tight", 0.25, 0.04, 0.03, 0.10),
    "natural": CutPolicy("natural", 0.45, 0.08, 0.06, 0.18),
    "relaxed": CutPolicy("relaxed", 0.80, 0.15, 0.10, 0.30),
}

FILLERS_IT = {"eh", "ehm", "ehh", "ehhh", "mh", "mmh", "mm", "mmm", "uhm", "uhmm", "umm", "hmm", "um", "uh", "er", "erm", "ah", "ahm"}
