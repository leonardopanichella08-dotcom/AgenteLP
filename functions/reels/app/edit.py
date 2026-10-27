"""Modifiche manuali dell'utente sul piano, con gli stessi vincoli di sicurezza dell'agente.

Regola: un taglio spostato a mano può muoversi solo attraverso silenzio. Se
l'intervallo spazzato contiene voce, la modifica è rifiutata (a meno di
`force`): è impossibile mozzare una parola per sbaglio dalla dashboard.
"""
from __future__ import annotations

from .audio_analysis import Envelope
from .config import POLICIES
from .cutting import CutInfo as DCut
from .cutting import SegSpec
from .planner import SegInput, SourceCtx, make_reel
from .schemas import CutInfo, EditPlan, Reel, Segment, SubtitleStyle
from .script_align import find_takes, tokens
from .cutting import build_segments


class EditError(ValueError):
    pass


def _to_dc(c: CutInfo) -> DCut:
    return DCut(c.asr_time, c.time, c.frame, c.method, tuple(c.silence) if c.silence else None, c.confidence, c.reason)


def _input(seg: Segment, ctx: SourceCtx) -> SegInput:
    idx = [k for k, w in enumerate(ctx.lex) if seg.src_start <= w.mid < seg.src_end]
    first, last = (idx[0], idx[-1]) if idx else (0, -1)
    spec = SegSpec(seg.src_start, seg.src_end, _to_dc(seg.cut_in), _to_dc(seg.cut_out), first, last,
                   seg.removed_before, list(seg.warnings))
    return SegInput(ctx, spec, seg.script_unit, seg.take_id, seg.removed_before)


def _sweep_is_silent(env: Envelope, a: float, b: float) -> bool:
    lo, hi = sorted((a, b))
    i0, i1 = env.idx(lo), env.idx(hi)
    return not bool(env.active[i0:i1 + 1].any())


def _rebuild(plan: EditPlan, reel: Reel, ctxs: dict[str, SourceCtx], inputs: list[SegInput], style: SubtitleStyle | None = None,
             sfx_on: bool | None = None, zoom_on: bool | None = None) -> Reel:
    fps = plan.exports[0].fps
    new = make_reel(reel.id, reel.title, reel.rank, inputs, ctxs, plan.exports, fps, style or reel.subtitles, reel.virality,
                    sfx_on=bool(reel.sfx) if sfx_on is None else sfx_on, social=reel.social.model_dump(),
                    zoom_on=bool(reel.zooms) if zoom_on is None else zoom_on)
    new.selected = reel.selected
    return new


def apply_ops(plan: EditPlan, reel_id: str, ops: list[dict], ctxs: dict[str, SourceCtx]) -> EditPlan:
    plan = plan.model_copy(deep=True)
    k = next((i for i, r in enumerate(plan.reels) if r.id == reel_id), None)
    if k is None:
        raise EditError(f"reel {reel_id} inesistente")
    reel = plan.reels[k]
    for op in ops:
        kind = op.get("op")
        if kind == "toggle_reel":
            reel.selected = bool(op["selected"])
        elif kind == "set_social":
            reel.social = reel.social.model_copy(update={x: op[x] for x in ("title", "caption", "hashtags") if x in op})
        elif kind == "set_style":
            upd = {x: op[x] for x in op if x != "op"}
            style = reel.subtitles.model_copy(update=upd)
            reel = _rebuild(plan, reel, ctxs, [_input(s, ctxs[s.source_id]) for s in reel.timeline], style=style)
        elif kind in ("set_sfx", "set_zoom"):
            reel = _rebuild(plan, reel, ctxs, [_input(s, ctxs[s.source_id]) for s in reel.timeline],
                            sfx_on=op["enabled"] if kind == "set_sfx" else None,
                            zoom_on=op["enabled"] if kind == "set_zoom" else None)
        elif kind == "remove_segment":
            if len(reel.timeline) <= 1:
                raise EditError("non si può rimuovere l'ultimo segmento")
            keep = [s for s in reel.timeline if s.id != op["segment_id"]]
            if len(keep) == len(reel.timeline):
                raise EditError("segmento inesistente")
            inputs = [_input(s, ctxs[s.source_id]) for s in keep]
            reel = _rebuild(plan, reel, ctxs, inputs)
        elif kind == "nudge":
            seg = next((s for s in reel.timeline if s.id == op["segment_id"]), None)
            if seg is None:
                raise EditError("segmento inesistente")
            ctx = ctxs[seg.source_id]
            fps = ctx.info.fps
            edge = op["edge"]
            cut = seg.cut_in if edge == "in" else seg.cut_out
            old = seg.src_start if edge == "in" else seg.src_end
            new_t = round((round(old * fps) + int(op["frames"])) / fps, 6)
            if not (0 <= new_t <= ctx.info.duration):
                raise EditError("fuori dal file")
            if not op.get("force") and not _sweep_is_silent(ctx.env, old, new_t):
                raise EditError("il taglio finirebbe dentro il parlato: sposta meno frame o usa 'force'")
            if edge == "in" and new_t >= seg.src_end - 1 / fps or edge == "out" and new_t <= seg.src_start + 1 / fps:
                raise EditError("segmento troppo corto")
            newcut = cut.model_copy(update={"time": new_t, "frame": round(new_t * fps), "method": "silence_gap",
                                            "reason": f"{cut.reason}+manuale", "confidence": 1.0})
            segs = []
            for s in reel.timeline:
                if s.id == seg.id:
                    s = s.model_copy(update={"src_start": new_t, "cut_in": newcut} if edge == "in" else {"src_end": new_t, "cut_out": newcut})
                segs.append(s)
            reel = _rebuild(plan, reel, ctxs, [_input(s, ctxs[s.source_id]) for s in segs])
        elif kind == "swap_take":
            reel = _swap_take(plan, reel, ctxs, int(op["unit"]), op["take_id"])
        else:
            raise EditError(f"operazione sconosciuta: {kind}")
    plan.reels[k] = reel
    return plan


def _swap_take(plan: EditPlan, reel: Reel, ctxs: dict[str, SourceCtx], unit: int, take_id: str) -> Reel:
    if plan.mode != "script_assembly":
        raise EditError("swap_take solo in modalità script")
    text = plan.script_report[unit].text
    toks = tokens(text)
    chosen = None
    for sid, ctx in ctxs.items():
        for t in find_takes(toks, ctx.lex, sid):
            if t.take_id == take_id:
                chosen = (ctx, t)
    if chosen is None:
        raise EditError("take non trovata")
    ctx, t = chosen
    policy = POLICIES[plan.cut_policy]
    specs = build_segments(ctx.lex, ctx.gaps, ctx.env, t.a, t.b, ctx.info.fps, policy, drop=t.drop, media_duration=ctx.info.duration)
    new_inputs = [SegInput(ctx, sp, unit, t.take_id, "take_change" if j == 0 else None) for j, sp in enumerate(specs)]
    out, placed = [], False
    for s in reel.timeline:
        if s.script_unit == unit:
            if not placed:
                out += new_inputs; placed = True
        else:
            out.append(_input(s, ctxs[s.source_id]))
    if not placed:
        raise EditError("unità non presente nel montaggio")
    for r in plan.script_report:
        if r.unit == unit:
            if r.chosen_take and r.chosen_take != t.take_id:
                r.alternatives = [a for a in r.alternatives if a["take_id"] != t.take_id] + \
                                 [{"take_id": r.chosen_take, "similarity": r.similarity, "score": r.similarity}]
            r.chosen_take, r.similarity = t.take_id, round(t.similarity, 3)
    return _rebuild(plan, reel, ctxs, out)
