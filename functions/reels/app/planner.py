"""Dal risultato dell'analisi all'Edit Plan JSON (timeline, parole, zoom, SFX, framing, social)."""
from __future__ import annotations

from dataclasses import dataclass, field

from . import reframe as rf
from .audio_analysis import Envelope
from .config import FORMATS, CutPolicy
from .cutting import Gap, SegSpec
from .media import MediaInfo
from .schemas import (CutInfo, ExportTarget, Framing, Keyframe, OutWord, Reel, Segment, SfxCue, Social,
                      SubtitleStyle, Transition, ViralityScore, ZoomRule)
from .textfeat import make_social, pick_emphasis, top_keywords
from .transcript import Word


@dataclass
class SourceCtx:
    id: str
    info: MediaInfo
    lex: list[Word]
    env: Envelope
    gaps: list[Gap]
    tracking: rf.TrackingResult | None = None
    speaker_map: dict[str, int] = field(default_factory=dict)
    speech: list[tuple[str, float, float]] = field(default_factory=list)


@dataclass
class SegInput:
    ctx: SourceCtx
    spec: SegSpec
    script_unit: int | None = None
    take_id: str | None = None
    removed_before: str | None = None   # sovrascrive spec.removed_before (es. take_change)


NUM_COLOR = 1   # indici in style.highlight_colors
POWER_COLOR = 2


def _cut(c) -> CutInfo:
    d = c.to_dict()
    d["silence"] = tuple(d["silence"]) if d["silence"] else None
    return CutInfo(**d)


def build_timeline(inputs: list[SegInput], fps_out: int) -> list[Segment]:
    segs: list[Segment] = []
    t = 0.0
    for k, si in enumerate(inputs):
        sp, fps = si.spec, si.ctx.info.fps
        n = max(1, round((sp.end - sp.start) * fps_out))
        dur = n / fps_out
        rb = si.removed_before or sp.removed_before
        segs.append(Segment(
            id=f"s{k + 1}", source_id=si.ctx.id, src_start=round(sp.start, 6), src_end=round(sp.end, 6),
            src_start_frame=round(sp.start * fps), src_end_frame=round(sp.end * fps),
            out_start=round(t, 6), out_end=round(t + dur, 6),
            cut_in=_cut(sp.cut_in), cut_out=_cut(sp.cut_out),
            removed_before=rb if k else None, script_unit=si.script_unit, take_id=si.take_id,
            warnings=list(sp.warnings)))
        t += dur
    return segs


def build_words(inputs: list[SegInput], segs: list[Segment], drops: dict[int, frozenset[int]] | None = None) -> list[OutWord]:
    out: list[OutWord] = []
    for si, sg in zip(inputs, segs):
        dur = sg.out_end - sg.out_start
        for k in range(si.spec.first_word, si.spec.last_word + 1):
            w = si.ctx.lex[k]
            s = min(max(w.start - si.spec.start, 0.0), dur)
            e = min(max(w.end - si.spec.start, 0.0), dur)
            if e - s < 0.03:
                continue
            out.append(OutWord(text=w.text, out_start=round(sg.out_start + s, 6), out_end=round(sg.out_start + e, 6),
                               src_start=round(w.start, 6), src_end=round(w.end, 6), speaker=w.speaker, segment_id=sg.id))
    return out


def apply_emphasis(words: list[OutWord], style: SubtitleStyle) -> None:
    proxy = [Word(w.text, w.src_start, w.src_end) for w in words]
    for i, (cat, emoji) in pick_emphasis(proxy).items():
        w = words[i]
        w.emphasis = "number" if cat == "number" else ("power" if cat == "power" else "keyword")
        idx = {"keyword": 0, "number": NUM_COLOR, "power": POWER_COLOR}[cat] % len(style.highlight_colors)
        w.color = style.highlight_colors[idx]
        w.emoji = emoji if style.emoji else None


def build_zooms(segs: list[Segment]) -> list[ZoomRule]:
    zs: list[ZoomRule] = []
    pattern_pause = [(1.00, 1.05), (1.12, 1.17)]               # alterna per nascondere i jump-cut
    pattern_scene = [(1.00, 1.08), (1.16, 1.06), (1.06, 1.14)]  # cambio concetto: in / out / in
    pi = si = 0
    for k, s in enumerate(segs):
        if k == 0 or s.removed_before in (None, "pause", "drop", "filler"):
            a, b = pattern_pause[pi % 2]; pi += 1
            reason = "segment_start" if k == 0 else "punch_in"
        else:
            a, b = pattern_scene[si % 3]; si += 1
            reason = "scene_change"
        zs.append(ZoomRule(out_start=s.out_start, out_end=s.out_end, from_scale=a, to_scale=b, easing="linear", reason=reason))
    return zs


def build_sfx(segs: list[Segment], words: list[OutWord], sfx_on: bool = True) -> tuple[list[SfxCue], list[Transition]]:
    trans: list[Transition] = []
    cues: list[SfxCue] = []
    last_t = -9.0
    for s in segs[1:]:
        scene = s.removed_before not in (None, "pause", "drop", "filler")
        trans.append(Transition(out_time=s.out_start, type="whoosh_cut" if scene else "cut"))
        if sfx_on and scene and s.out_start - last_t >= 1.2:
            cues.append(SfxCue(out_time=max(0.0, round(s.out_start - 0.06, 3)), sfx_id="whoosh", gain_db=-14,
                               reason="cambio di concetto/unità"))
            last_t = s.out_start
    if sfx_on:
        for w in words:
            if w.emphasis in ("number", "power") and w.out_start - last_t >= 1.8:
                cues.append(SfxCue(out_time=round(w.out_start, 3), sfx_id="ding" if w.emphasis == "number" else "pop",
                                   gain_db=-16, reason=f"parola d'impatto ({w.emphasis})", anchor_word=w.text))
                last_t = w.out_start
    cues.sort(key=lambda c: c.out_time)
    return cues, trans


def build_framing(ctxs: dict[str, SourceCtx], segs: list[Segment], export: ExportTarget) -> Framing:
    fm = FORMATS[export.format_id]
    # un solo sorgente per decidere la strategia: quello che copre più durata
    dur_by = {}
    for s in segs:
        dur_by[s.source_id] = dur_by.get(s.source_id, 0) + (s.out_end - s.out_start)
    main = ctxs[max(dur_by, key=dur_by.get)]
    cov = main.tracking.coverage if main.tracking else 0.0
    strat, why = rf.choose_strategy(export.reframe.strategy, main.info.width, main.info.height, fm.aspect, cov)
    framing = Framing(format_id=export.format_id, strategy=strat, reason=why, blur_sigma=export.reframe.blur_sigma)  # type: ignore[arg-type]
    if strat != "smart_crop":
        return framing
    for s in segs:
        ctx = ctxs[s.source_id]
        cw, ch = rf.crop_window(ctx.info.width, ctx.info.height, fm.aspect)
        if not ctx.tracking or not ctx.tracking.tracks:
            kf = [{"t": 0.0, "x": (ctx.info.width - cw) / 2, "y": (ctx.info.height - ch) / 2, "w": cw, "h": ch}]
            framing.crop_keyframes[s.id] = [Keyframe(**k) for k in kf]
            continue
        path = rf.build_path(ctx.tracking, ctx.speaker_map, ctx.speech, cw, ch, export.reframe.smooth)
        kf = rf.keyframes_for_segment(path, s.src_start, s.src_end, cw, ch, ctx.info.width, ctx.info.height)
        framing.crop_keyframes[s.id] = [Keyframe(**k) for k in kf]
        followed = sorted({str(t) for t in path.speaker_track[(path.t >= s.src_start) & (path.t <= s.src_end)] if t >= 0})
        framing.active_speaker[s.id] = followed
    return framing


def make_reel(reel_id: str, title: str, rank: int, inputs: list[SegInput], ctxs: dict[str, SourceCtx],
              exports: list[ExportTarget], fps_out: int, style: SubtitleStyle, virality: ViralityScore | None,
              hook_text: str = "", sfx_on: bool = True, social: dict | None = None,
              extra_keywords: list[str] | None = None, zoom_on: bool = True) -> Reel:
    segs = build_timeline(inputs, fps_out)
    words = build_words(inputs, segs)
    apply_emphasis(words, style)
    zooms = build_zooms(segs) if zoom_on else []
    cues, trans = build_sfx(segs, words, sfx_on)
    framing = [build_framing(ctxs, segs, e) for e in exports]
    text = " ".join(w.text for w in words)
    proxy = [Word(w.text, w.src_start, w.src_end) for w in words]
    kw = (extra_keywords or []) + top_keywords(proxy)
    soc = social or make_social(text, kw, hook_text or title)
    warnings = [w for s in segs for w in s.warnings]
    return Reel(id=reel_id, title=title, rank=rank, duration=round(segs[-1].out_end, 6) if segs else 0.0,
                virality=virality, timeline=segs, words=words, transcript=text, framing=framing, subtitles=style,
                zooms=zooms, sfx=cues, transitions=trans, social=Social(**soc), warnings=warnings)
