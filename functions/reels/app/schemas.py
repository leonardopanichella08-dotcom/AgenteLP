"""Universal Edit Plan: il contratto JSON tra agente e backend di rendering.

Tutti i tempi sono in secondi sulla timeline indicata nel nome:
  src_*  -> tempo nel file sorgente
  out_*  -> tempo nel reel montato (dopo i tagli)
I tagli sono anche espressi in frame (src_*_frame) per garantire frame-accuracy.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

SCHEMA_VERSION = "1.0"
Mode = Literal["script_assembly", "long_form_extraction"]
FormatId = Literal["9:16", "4:5", "1:1", "16:9"]


class Source(BaseModel):
    id: str
    path: str
    duration: float
    fps: float
    width: int
    height: int
    has_audio: bool = True


class ReframeOptions(BaseModel):
    strategy: Literal["auto", "smart_crop", "blur_pad"] = "auto"
    blur_sigma: int = Field(30, ge=0, le=80)
    smooth: float = Field(0.85, ge=0, le=0.99, description="0=reattivo, 0.99=camera ferma")


class ExportTarget(BaseModel):
    format_id: FormatId
    width: int
    height: int
    fps: int = 30
    platforms: list[str] = []
    reframe: ReframeOptions = ReframeOptions()


class CutInfo(BaseModel):
    asr_time: float = Field(description="dove avrebbe tagliato un editor ingenuo (timestamp ASR)")
    time: float = Field(description="taglio finale, nel silenzio reale e agganciato al frame")
    frame: int
    method: Literal["silence_gap", "valley", "file_edge"]
    silence: tuple[float, float] | None = None
    confidence: float = Field(ge=0, le=1)
    reason: str


class Segment(BaseModel):
    id: str
    source_id: str
    src_start: float
    src_end: float
    src_start_frame: int
    src_end_frame: int
    out_start: float
    out_end: float
    cut_in: CutInfo
    cut_out: CutInfo
    removed_before: Literal["pause", "drop", "filler", "take_change"] | None = None
    script_unit: int | None = None
    take_id: str | None = None
    warnings: list[str] = []


class OutWord(BaseModel):
    text: str
    out_start: float
    out_end: float
    src_start: float
    src_end: float
    speaker: str | None = None
    segment_id: str
    emphasis: Literal["none", "keyword", "number", "power"] = "none"
    color: str | None = None
    emoji: str | None = None


class ViralityScore(BaseModel):
    score: int = Field(ge=0, le=100)
    reasons: list[str]
    hook_text: str = ""
    signals: dict[str, float] = {}


class Keyframe(BaseModel):
    t: float = Field(description="secondi dall'inizio del segmento")
    x: float
    y: float
    w: float
    h: float


class Framing(BaseModel):
    format_id: FormatId
    strategy: Literal["none", "smart_crop", "blur_pad"]
    reason: str
    crop_keyframes: dict[str, list[Keyframe]] = Field(
        default={}, description="per segment_id: finestra di crop in pixel sorgente (interpolazione lineare)")
    active_speaker: dict[str, list[str]] = Field(default={}, description="segment_id -> speaker seguiti")
    blur_sigma: int = 30


class SubtitleStyle(BaseModel):
    preset: Literal["hormozi", "mrbeast", "clean", "karaoke"] = "hormozi"
    font: str = "Inter"
    font_size_pct: float = Field(0.062, description="altezza font / altezza frame")
    uppercase: bool = True
    max_words_per_line: int = 3
    primary_color: str = "#FFFFFF"
    highlight_colors: list[str] = ["#FFE600", "#00E676", "#FF3B30"]
    outline_color: str = "#000000"
    outline_px: float = 0.008
    pop_scale: float = 1.18
    position_y: float = Field(0.66, description="centro riga, frazione dell'altezza (0=alto)")
    safe_top: float = 0.1
    safe_bottom: float = 0.22
    emoji: bool = True


class ZoomRule(BaseModel):
    out_start: float
    out_end: float
    from_scale: float = 1.0
    to_scale: float = 1.12
    easing: Literal["linear", "ease_out"] = "ease_out"
    reason: Literal["segment_start", "emphasis", "scene_change", "punch_in"]
    anchor: tuple[float, float] = (0.5, 0.45)


class SfxCue(BaseModel):
    out_time: float
    sfx_id: Literal["whoosh", "pop", "ding", "click", "riser"]
    gain_db: float = -12.0
    reason: str
    anchor_word: str | None = None


class Broll(BaseModel):
    out_start: float
    out_end: float
    query: str
    asset_path: str | None = None
    provider: Literal["pexels", "shutterstock", "local"] = "pexels"
    layout: Literal["fullscreen", "pip"] = "fullscreen"


class Transition(BaseModel):
    out_time: float
    type: Literal["cut", "fade", "whoosh_cut"] = "cut"
    duration: float = 0.0


class Social(BaseModel):
    title: str
    caption: str
    hashtags: list[str]


class Reel(BaseModel):
    id: str
    title: str
    rank: int
    duration: float
    virality: ViralityScore | None = None
    timeline: list[Segment]
    words: list[OutWord]
    transcript: str
    framing: list[Framing]
    subtitles: SubtitleStyle
    zooms: list[ZoomRule]
    sfx: list[SfxCue]
    broll: list[Broll] = []
    transitions: list[Transition]
    social: Social
    selected: bool = True
    warnings: list[str] = []


class ScriptUnitReport(BaseModel):
    unit: int
    text: str
    status: Literal["matched", "weak", "missing"]
    chosen_take: str | None = None
    similarity: float = 0.0
    alternatives: list[dict] = []


class EditPlan(BaseModel):
    schema_version: str = SCHEMA_VERSION
    project_id: str
    mode: Mode
    cut_policy: Literal["tight", "natural", "relaxed"] = "natural"
    sources: list[Source]
    exports: list[ExportTarget]
    reels: list[Reel]
    script_report: list[ScriptUnitReport] = []
    diagnostics: dict = {}


def json_schema() -> dict:
    return EditPlan.model_json_schema()
