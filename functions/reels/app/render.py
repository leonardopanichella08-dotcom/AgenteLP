"""Edit Plan → MP4 con FFmpeg (un solo filter_complex, un solo encode).

Frame-accuracy: ogni segmento è `trim` sul tempo sorgente (mezzo frame di
tolleranza all'ingresso, così il frame al taglio non viene perso per
arrotondamento) e poi bloccato a N frame esatti di output; l'audio dello
stesso segmento è bloccato a N/fps secondi. Audio e video non possono
derivare nemmeno concatenando decine di segmenti.
"""
from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Callable

from .config import FORMATS
from .schemas import EditPlan, ExportTarget, Framing, Reel, Segment, SubtitleStyle
from .sfx import ensure_sfx
from .subtitles import build_ass

FADE = 0.006    # s: micro-fade audio ai tagli (anti-click)


def _even(v: float) -> int:
    return max(2, int(round(v / 2)) * 2)


def _lerp_expr(kfs: list, attr: str) -> str:
    """Interpolazione lineare a tratti in funzione di `t` (secondi dall'inizio del segmento)."""
    vals = [(k.t, getattr(k, attr)) for k in kfs]
    if len(vals) == 1:
        return f"{vals[0][1]:.2f}"
    expr = f"{vals[-1][1]:.2f}"
    for (t0, v0), (t1, v1) in reversed(list(zip(vals, vals[1:]))):
        dt = max(t1 - t0, 1e-3)
        expr = f"if(lt(t,{t1:.3f}),{v0:.2f}+({v1 - v0:.2f})*(t-{t0:.3f})/{dt:.3f},{expr})"
    return expr


def _zoom_expr(a: float, b: float, dur: float) -> str | None:
    if abs(a - 1) < 1e-3 and abs(b - 1) < 1e-3:
        return None
    return f"({a:.4f}+({b - a:.4f})*min(t/{max(dur, 0.04):.3f},1))"


def _segment_zoom(reel: Reel, seg: Segment) -> tuple[float, float]:
    for z in reel.zooms:
        if abs(z.out_start - seg.out_start) < 1e-3:
            return z.from_scale, z.to_scale
    return 1.0, 1.0


def _video_chain(k: int, in_label: str, seg: Segment, fr: Framing, src_w: int, src_h: int, src_fps: float,
                 W: int, H: int, fps: int, zoom: tuple[float, float], use_zoom: bool) -> list[str]:
    n = max(1, round((seg.out_end - seg.out_start) * fps))
    dur = n / fps
    h = 0.5 / src_fps
    s0, s1 = max(seg.src_start - h, 0.0), seg.src_end - h
    base = (f"[{in_label}]trim=start={s0:.5f}:end={s1:.5f},setpts=PTS-STARTPTS,fps={fps},"
            f"trim=end_frame={n},setpts=PTS-STARTPTS")
    z = _zoom_expr(*zoom, dur) if use_zoom else None
    out: list[str] = []
    if fr.strategy == "smart_crop":
        kfs = fr.crop_keyframes.get(seg.id) or []
        if not kfs:
            raise ValueError(f"smart_crop senza keyframe per {seg.id}")
        cw, ch = _even(kfs[0].w), _even(kfs[0].h)
        chain = (f"{base},crop=w={cw}:h={ch}:x='{_lerp_expr(kfs, 'x')}':y='{_lerp_expr(kfs, 'y')}':exact=1,"
                 f"scale={W}:{H}:flags=lanczos")
        if z:
            chain += f",scale=w='trunc({W}*{z}/2)*2':h='trunc({H}*{z}/2)*2':eval=frame:flags=bilinear,crop={W}:{H}"
        out.append(f"{chain},setsar=1[v{k}]")
    elif fr.strategy == "none":
        chain = f"{base},scale={W}:{H}:flags=lanczos"
        if z:
            chain += f",scale=w='trunc({W}*{z}/2)*2':h='trunc({H}*{z}/2)*2':eval=frame:flags=bilinear,crop={W}:{H}"
        out.append(f"{chain},setsar=1[v{k}]")
    else:  # blur_pad: sfondo = stesso video sfocato, in primo piano il frame intero
        sc = min(W / src_w, H / src_h)
        fw, fh = _even(src_w * sc), _even(src_h * sc)
        sig = max(2, int(fr.blur_sigma / 8))
        out.append(f"{base},split[bi{k}][fi{k}]")
        out.append(f"[bi{k}]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},"
                   f"scale=iw/10:ih/10,boxblur={sig}:2,scale={W}:{H},eq=brightness=-0.06:saturation=1.1[bg{k}]")
        if z:
            out.append(f"[fi{k}]scale=w='trunc({fw}*{z}/2)*2':h='trunc({fh}*{z}/2)*2':eval=frame:flags=bilinear[fg{k}]")
        else:
            out.append(f"[fi{k}]scale={fw}:{fh}:flags=lanczos[fg{k}]")
        out.append(f"[bg{k}][fg{k}]overlay=x=(W-w)/2:y=(H-h)/2,setsar=1[v{k}]")
    return out


def _audio_chain(k: int, in_label: str, seg: Segment, fps: int) -> str:
    n = max(1, round((seg.out_end - seg.out_start) * fps))
    dur = n / fps
    return (f"[{in_label}]atrim=start={seg.src_start:.6f}:end={seg.src_start + dur:.6f},asetpts=PTS-STARTPTS,"
            f"aresample=48000,apad=whole_dur={dur:.6f},atrim=end={dur:.6f},"
            f"afade=t=in:d={FADE},afade=t=out:st={max(dur - FADE, 0):.6f}:d={FADE}[a{k}]")


def build_graph(plan: EditPlan, reel: Reel, export: ExportTarget, src_paths: dict[str, str], ass_path: Path | None,
                sfx_paths: dict[str, Path], out_scale: float = 1.0, broll_inputs: list[tuple[Path, float, float]] | None = None,
                use_zoom: bool = True, loudnorm: bool = True) -> tuple[list[str], str]:
    """Ritorna (argomenti -i, testo del filter_complex)."""
    fm_id = export.format_id
    fr = next(f for f in reel.framing if f.format_id == fm_id)
    W, H = _even(export.width * out_scale), _even(export.height * out_scale)
    fps = export.fps
    srcs = {s.id: s for s in plan.sources}
    order = list(dict.fromkeys(s.source_id for s in reel.timeline))
    idx = {sid: i for i, sid in enumerate(order)}
    uses = {sid: [k for k, s in enumerate(reel.timeline) if s.source_id == sid] for sid in order}

    inputs: list[str] = []
    for sid in order:
        inputs += ["-i", src_paths[sid]]
    lines: list[str] = []

    # split per sorgente (un decode, N rami trim)
    for sid in order:
        i, m = idx[sid], len(uses[sid])
        if m == 1:
            lines.append(f"[{i}:v]null[sv{i}_0]")
            lines.append(f"[{i}:a]anull[sa{i}_0]")
        else:
            lines.append(f"[{i}:v]split={m}" + "".join(f"[sv{i}_{j}]" for j in range(m)))
            lines.append(f"[{i}:a]asplit={m}" + "".join(f"[sa{i}_{j}]" for j in range(m)))
    for k, seg in enumerate(reel.timeline):
        src = srcs[seg.source_id]
        i = idx[seg.source_id]; j = uses[seg.source_id].index(k)
        lines += _video_chain(k, f"sv{i}_{j}", seg, fr, src.width, src.height, src.fps, W, H, fps,
                              _segment_zoom(reel, seg), use_zoom)
        lines.append(_audio_chain(k, f"sa{i}_{j}", seg, fps))
    K = len(reel.timeline)
    lines.append("".join(f"[v{k}][a{k}]" for k in range(K)) + f"concat=n={K}:v=1:a=1[vc][ac]")

    vlabel = "vc"
    n_in = len(order)
    for b, (path, s, e) in enumerate(broll_inputs or []):
        inputs += ["-stream_loop", "-1", "-i", str(path)]
        lines.append(f"[{n_in}:v]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},"
                     f"setpts=PTS-STARTPTS+{s:.3f}/TB,fps={fps}[br{b}]")
        lines.append(f"[{vlabel}][br{b}]overlay=enable='between(t,{s:.3f},{e:.3f})':eof_action=pass[vb{b}]")
        vlabel = f"vb{b}"; n_in += 1
    if ass_path is not None:
        lines.append(f"[{vlabel}]ass=filename='{ass_path}'[vs]")
        vlabel = "vs"
    lines.append(f"[{vlabel}]format=yuv420p[vout]")

    # audio: voce + SFX
    alabel = "ac"
    mix_in = []
    for c, cue in enumerate(reel.sfx):
        inputs += ["-i", str(sfx_paths[cue.sfx_id])]
        ms = int(round(cue.out_time * 1000))
        lines.append(f"[{n_in}:a]adelay={ms}|{ms},volume={cue.gain_db}dB[sx{c}]")
        mix_in.append(f"[sx{c}]"); n_in += 1
    if mix_in:
        lines.append(f"[ac]{''.join(mix_in)}amix=inputs={1 + len(mix_in)}:normalize=0:duration=first:dropout_transition=0[am]")
        alabel = "am"
    if loudnorm:
        lines.append(f"[{alabel}]loudnorm=I=-14:TP=-1.5:LRA=11[aout]")
    else:
        lines.append(f"[{alabel}]anull[aout]")
    return inputs, ";\n".join(lines)


def render_reel(plan: EditPlan, reel: Reel, export: ExportTarget, out_path: Path, work_dir: Path,
                quality: str = "final", progress: Callable[[float], None] | None = None) -> Path:
    try:
        return _render(plan, reel, export, out_path, work_dir, quality, progress, loudnorm=True)
    except RuntimeError as e:
        if "NaN" not in str(e):      # loudnorm va in NaN su silenzio digitale puro
            raise
        return _render(plan, reel, export, out_path, work_dir, quality, progress, loudnorm=False)


def _render(plan: EditPlan, reel: Reel, export: ExportTarget, out_path: Path, work_dir: Path, quality: str,
            progress: Callable[[float], None] | None, loudnorm: bool) -> Path:
    work_dir.mkdir(parents=True, exist_ok=True)
    draft = quality == "draft"
    scale = 0.5 if draft else 1.0
    W, H = _even(export.width * scale), _even(export.height * scale)
    ass = work_dir / f"{reel.id}_{export.format_id.replace(':', 'x')}.ass"
    fm = FORMATS[export.format_id]
    style = reel.subtitles.model_copy(update={"position_y": reel.subtitles.position_y,
                                              "safe_top": fm.safe_top, "safe_bottom": fm.safe_bottom})
    ass.write_text(build_ass(reel.words, style, W, H), encoding="utf-8")
    sfx = ensure_sfx(work_dir.parent / "_sfx")
    broll = [(Path(b.asset_path), b.out_start, b.out_end) for b in reel.broll if b.asset_path and Path(b.asset_path).exists()]
    src_paths = {s.id: s.path for s in plan.sources}
    inputs, graph = build_graph(plan, reel, export, src_paths, ass, sfx, scale, broll, loudnorm=loudnorm)
    script = work_dir / f"{reel.id}_{export.format_id.replace(':', 'x')}.filtergraph"
    script.write_text(graph)
    cmd = ["ffmpeg", "-y", "-v", "error", "-nostats", "-progress", "pipe:1", *inputs,
           "-filter_complex_script", str(script), "-map", "[vout]", "-map", "[aout]",
           "-c:v", "libx264", "-preset", "ultrafast" if draft else "medium", "-crf", "28" if draft else "18",
           "-r", str(export.fps), "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
           "-movflags", "+faststart", "-t", f"{reel.duration:.4f}", str(out_path)]
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    total_us = reel.duration * 1e6
    assert p.stdout is not None
    for line in p.stdout:
        if line.startswith("out_time_us=") and progress:
            try:
                progress(min(1.0, max(0.0, int(line.split("=")[1]) / total_us)))
            except ValueError:
                pass
    err = p.stderr.read() if p.stderr else ""
    if p.wait() != 0:
        raise RuntimeError(f"ffmpeg ha fallito:\n{err[-2000:]}")
    return out_path
