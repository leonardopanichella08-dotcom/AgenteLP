"""Orchestrazione end-to-end: sorgenti → Edit Plan."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from . import asr as asr_mod
from . import reframe as rf
from .audio_analysis import compute_envelope
from .config import FORMATS, POLICIES
from .cutting import SegSpec, analyze_gaps, build_segments, split_sentences
from .extractor import Candidate, edited_duration, find_candidates, score_window, select_top
from .llm import LLM, validate_picks
from .media import probe, read_audio
from . import broll as broll_mod
from .planner import SegInput, SourceCtx, make_reel
from .schemas import (EditPlan, ExportTarget, ReframeOptions, ScriptUnitReport, Source, SubtitleStyle, ViralityScore)
from .script_align import choose_takes, split_script
from .transcript import Transcript, lexical

STAGES = [("probe", "Analisi file"), ("transcribe", "Trascrizione"), ("audio", "Analisi audio"),
          ("cuts", "Scelta dei tagli"), ("faces", "Tracking volti"), ("plan", "Piano di montaggio")]

Progress = Callable[[str, float, str], None]


@dataclass
class Options:
    mode: str = "long_form_extraction"
    formats: list[str] = field(default_factory=lambda: ["9:16"])
    cut_policy: str = "natural"
    reframe: str = "auto"
    subtitle_preset: str = "hormozi"
    n_min: int = 3
    n_max: int = 5
    min_dur: float = 15.0
    max_dur: float = 60.0
    fps: int = 30
    language: str = "it"
    sfx: bool = True
    emoji: bool = True
    zoom: bool = True
    broll: bool = False
    script: str | None = None


def _preset(name: str, fmt_id: str) -> SubtitleStyle:
    f = FORMATS[fmt_id]
    base = SubtitleStyle(preset=name, position_y=f.sub_y, safe_top=f.safe_top, safe_bottom=f.safe_bottom)  # type: ignore[arg-type]
    if name == "mrbeast":
        return base.model_copy(update={"highlight_colors": ["#FFD400", "#00E5FF", "#FF2D95"], "font_size_pct": 0.07, "max_words_per_line": 2})
    if name == "clean":
        return base.model_copy(update={"uppercase": False, "font_size_pct": 0.05, "max_words_per_line": 6})
    return base


def _speech_intervals(lex) -> list[tuple[str, float, float]]:
    out: list[tuple[str, float, float]] = []
    for w in lex:
        if not w.speaker:
            continue
        if out and out[-1][0] == w.speaker and w.start - out[-1][2] < 1.0:
            out[-1] = (w.speaker, out[-1][1], w.end)
        else:
            out.append((w.speaker, w.start, w.end))
    return out


class Pipeline:
    def __init__(self, project_id: str, sources: list[tuple[str, str]], opts: Options, progress: Progress | None = None,
                 asr: asr_mod.ASR | None = None, detector: rf.FaceDetector | None = None, llm: LLM | None = None,
                 transcripts: dict[str, Transcript] | None = None, broll_provider=None, work_dir: Path | None = None):
        self.pid, self.src_list, self.o = project_id, sources, opts
        self.progress = progress or (lambda *_: None)
        self.asr, self.detector, self.llm = asr, detector, llm
        self.transcripts = transcripts or {}
        self.broll_provider = broll_provider
        self.work_dir = work_dir or Path("data") / "_broll"
        self.policy = POLICIES[opts.cut_policy]
        self.ctxs: dict[str, SourceCtx] = {}
        self.used_transcripts: dict[str, Transcript] = {}
        self.diag: dict = {}

    # ── fasi ──────────────────────────────────────────────────────────────
    def _load(self) -> list[Source]:
        sources: list[Source] = []
        n = len(self.src_list)
        for i, (sid, path) in enumerate(self.src_list):
            self.progress("probe", i / n, f"Leggo {Path(path).name}")
            info = probe(path)
            sources.append(Source(id=sid, path=path, duration=info.duration, fps=info.fps, width=info.width,
                                  height=info.height, has_audio=info.has_audio))
            self.progress("transcribe", i / n, f"Trascrivo {Path(path).name}")
            tr = self.transcripts.get(sid) or asr_mod.transcribe(path, sid, self.o.language, self.asr)
            self.used_transcripts[sid] = tr
            lex = lexical(tr.words)
            if not lex:
                raise ValueError(f"{sid}: nessuna parola riconosciuta")
            self.progress("audio", i / n, "Cerco i silenzi reali nell'audio")
            env = compute_envelope(read_audio(path, 16000), 16000)
            gaps = analyze_gaps(lex, env, self.policy)
            self.ctxs[sid] = SourceCtx(sid, info, lex, env, gaps, speech=_speech_intervals(lex))
        return sources

    def _exports(self) -> list[ExportTarget]:
        return [ExportTarget(format_id=f, width=FORMATS[f].width, height=FORMATS[f].height, fps=self.o.fps,  # type: ignore[arg-type]
                             platforms=list(FORMATS[f].platforms), reframe=ReframeOptions(strategy=self.o.reframe))  # type: ignore[arg-type]
                for f in self.o.formats]

    def _track(self, used: dict[str, list[tuple[float, float]]], exports: list[ExportTarget]) -> None:
        for sid, ranges in used.items():
            ctx = self.ctxs[sid]
            need = any(FORMATS[e.format_id].aspect < ctx.info.width / ctx.info.height - 0.02 and e.reframe.strategy != "blur_pad"
                       for e in exports)
            if not need:
                continue
            self.progress("faces", 0.0, "Rilevo i volti e il parlante attivo")
            try:
                merged = _merge_ranges(ranges)
                ctx.tracking = rf.track_faces(ctx.info.path, merged, self.detector,
                                              lambda f: self.progress("faces", f, "Rilevo i volti e il parlante attivo"))
                ctx.speaker_map = rf.assign_speakers(ctx.tracking, ctx.speech)
                self.diag[f"tracking_{sid}"] = {"tracks": len(ctx.tracking.tracks), "coverage": round(ctx.tracking.coverage, 2),
                                                "speaker_map": ctx.speaker_map}
            except Exception as e:  # OpenCV assente o video illeggibile → blur_pad
                self.diag[f"tracking_{sid}"] = {"error": str(e)}

    # ── modalità B ────────────────────────────────────────────────────────
    def _mode_b(self, exports: list[ExportTarget]):
        o = self.o
        pool: list[tuple[str, Candidate, list]] = []
        llm_meta: dict[tuple[str, int, int], dict] = {}
        for sid, ctx in self.ctxs.items():
            sents = split_sentences(ctx.lex, ctx.gaps)
            cands = find_candidates(sents, ctx.lex, ctx.gaps, ctx.env, ctx.info.fps, self.policy, ctx.info.duration,
                                    o.min_dur, o.max_dur)
            self.diag[f"candidates_{sid}"] = len(cands)
            if self.llm:
                try:
                    picks = validate_picks(self.llm.select_clips(sents, o.n_min, o.n_max, o.min_dur, o.max_dur, o.language), len(sents))
                    for p in picks:
                        win = sents[p["start_sentence"]:p["end_sentence"] + 1]
                        segs = build_segments(ctx.lex, ctx.gaps, ctx.env, win[0].a, win[-1].b, ctx.info.fps, self.policy,
                                              media_duration=ctx.info.duration)
                        dur = edited_duration(segs)
                        if segs and o.min_dur <= dur <= o.max_dur:
                            sc, rs, sg = score_window(win, ctx.lex, segs, dur, o.min_dur, o.max_dur)
                            c = Candidate(p["start_sentence"], p["end_sentence"], segs, dur, float(p["virality_score"]),
                                          list(p["reasons"]) or rs, sg, p.get("hook_text") or win[0].text, " ".join(s.text for s in win),
                                          meta={"llm": p})
                            pool.append((sid, c, sents))
                            continue
                except Exception as e:
                    self.diag["llm_error"] = str(e)
            for c in select_top(cands, o.n_min, o.n_max):
                pool.append((sid, c, sents))
        # globali: migliori per punteggio, senza sovrapposizioni nella stessa sorgente
        chosen: list[tuple[str, Candidate, list]] = []
        for sid, c, sents in sorted(pool, key=lambda x: -x[1].score):
            if all(sid != s2 or c.s_b < c2.s_a or c.s_a > c2.s_b for s2, c2, _ in chosen):
                chosen.append((sid, c, sents))
            if len(chosen) >= o.n_max:
                break
        used: dict[str, list[tuple[float, float]]] = {}
        for sid, c, _ in chosen:
            used.setdefault(sid, []).extend((s.start, s.end) for s in c.segs)
        self._track(used, exports)
        self.progress("plan", 0.0, "Costruisco il piano di montaggio")
        reels = []
        for rank, (sid, c, _) in enumerate(chosen, 1):
            ctx = self.ctxs[sid]
            style = _preset(o.subtitle_preset, o.formats[0]); style.emoji = o.emoji
            llm_p = c.meta.get("llm", {})
            social = None
            kw = list(llm_p.get("keywords", []))
            if llm_p.get("caption"):
                social = {"title": llm_p["title"], "caption": llm_p["caption"], "hashtags": llm_p["hashtags"]}
            elif self.llm:
                try:
                    e = self.llm.enrich(c.text, o.language)
                    social = {"title": e["title"], "caption": e["caption"], "hashtags": e["hashtags"]}; kw = e.get("keywords", [])
                except Exception as ex:
                    self.diag["llm_error"] = str(ex)
            reels.append(make_reel(
                f"reel{rank}", (llm_p.get("title") or c.hook_text)[:80], rank, [SegInput(ctx, s) for s in c.segs],
                self.ctxs, exports, o.fps, style,
                ViralityScore(score=int(round(c.score)), reasons=c.reasons or ["Segmento compiuto con buon ritmo"],
                              hook_text=c.hook_text, signals=c.signals),
                hook_text=c.hook_text, sfx_on=o.sfx, social=social, extra_keywords=kw, zoom_on=o.zoom))
        if len(reels) < o.n_min:
            self.diag["warning"] = f"trovati solo {len(reels)} spezzoni validi (richiesti almeno {o.n_min}): sorgente troppo breve o pochi punti di chiusura puliti"
        return reels, []

    # ── modalità A ────────────────────────────────────────────────────────
    def _mode_a(self, exports: list[ExportTarget]):
        o = self.o
        units = split_script(o.script or "")
        if not units:
            raise ValueError("Modalità A richiede uno script")
        res = choose_takes(units, {sid: c.lex for sid, c in self.ctxs.items()})
        inputs: list[SegInput] = []
        report: list[ScriptUnitReport] = []
        for r in res:
            ch = r["chosen"]
            alts = [{"take_id": t.take_id, "similarity": round(t.similarity, 3), "score": round(t.score, 3)}
                    for t in r["candidates"] if ch is None or t.take_id != ch.take_id][:5]
            report.append(ScriptUnitReport(unit=r["unit"], text=r["text"], status=r["status"],
                                           chosen_take=ch.take_id if ch else None,
                                           similarity=round(ch.similarity, 3) if ch else 0.0, alternatives=alts))
            if ch is None:
                continue
            ctx = self.ctxs[ch.source_id]
            segs = build_segments(ctx.lex, ctx.gaps, ctx.env, ch.a, ch.b, ctx.info.fps, self.policy, drop=ch.drop,
                                  media_duration=ctx.info.duration)
            for k, sp in enumerate(segs):
                inputs.append(SegInput(ctx, sp, script_unit=r["unit"], take_id=ch.take_id,
                                       removed_before="take_change" if k == 0 and inputs else None))
        if not inputs:
            raise ValueError("Nessuna frase dello script trovata nelle clip")
        used: dict[str, list[tuple[float, float]]] = {}
        for si in inputs:
            used.setdefault(si.ctx.id, []).append((si.spec.start, si.spec.end))
        self._track(used, exports)
        self.progress("plan", 0.0, "Costruisco il piano di montaggio")
        style = _preset(o.subtitle_preset, o.formats[0]); style.emoji = o.emoji
        title = units[0][:60]
        kw = []
        reel = make_reel("reel1", title, 1, inputs, self.ctxs, exports, o.fps, style, None, hook_text=units[0],
                         sfx_on=o.sfx, extra_keywords=kw, zoom_on=o.zoom)
        missing = [x.unit for x in report if x.status == "missing"]
        if missing:
            reel.warnings.append(f"Frasi dello script non trovate nelle clip: {missing}")
        return [reel], report

    def run(self) -> EditPlan:
        sources = self._load()
        exports = self._exports()
        self.progress("cuts", 0.0, "Scelgo i punti di taglio")
        reels, report = self._mode_a(exports) if self.o.mode == "script_assembly" else self._mode_b(exports)
        if self.o.broll:
            prov = self.broll_provider or broll_mod.PexelsClient.from_env()
            if prov is None:
                self.diag["broll"] = "PEXELS_API_KEY mancante: B-roll saltato"
            else:
                for r in reels:
                    r.broll = broll_mod.plan_windows(r)
                    r.warnings += broll_mod.resolve(r, prov, self.work_dir)
        self.progress("plan", 1.0, "Piano pronto")
        return EditPlan(project_id=self.pid, mode=self.o.mode, cut_policy=self.o.cut_policy,  # type: ignore[arg-type]
                        sources=sources, exports=exports, reels=reels, script_report=report, diagnostics=self.diag)


def _merge_ranges(rs: list[tuple[float, float]], gap: float = 0.5) -> list[tuple[float, float]]:
    out: list[tuple[float, float]] = []
    for s, e in sorted(rs):
        if out and s - out[-1][1] <= gap:
            out[-1] = (out[-1][0], max(out[-1][1], e))
        else:
            out.append((s, e))
    return out
