"""Esecuzione in background di analisi e render."""
from __future__ import annotations

import json
import traceback
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from . import reframe as rf
from .asr import ASRUnavailable
from .llm import get_llm
from .pipeline import STAGES, Options, Pipeline
from .render import render_reel
from .store import Project
from .transcript import Transcript

POOL = ThreadPoolExecutor(max_workers=2, thread_name_prefix="reels")


class _BoxDetector:
    def __init__(self, boxes: list[tuple[float, float, float, float]]):
        self.boxes = boxes

    def detect(self, frame):
        return self.boxes


def submit_analysis(p: Project) -> None:
    POOL.submit(run_analysis, p)


def run_analysis(p: Project) -> None:
    st = p.status()
    p.update(status="analyzing", error=None)
    try:
        o = Options(**st["options"])
        srcs = [(s["id"], str(p.src_dir / s["filename"])) for s in st["sources"]]
        det = None
        if st.get("demo_faces"):                         # modalità demo: volti sintetici noti
            det = _BoxDetector([tuple(b) for b in st["demo_faces"]])
        pipe = Pipeline(p.id, srcs, o, progress=lambda s, f, m: p.update_stage(s, f, m, STAGES), detector=det, llm=get_llm(), work_dir=p.work_dir / "broll")
        plan = pipe.run()
        p.save_context(pipe.ctxs, pipe.used_transcripts)
        p.save_plan(plan)
        p.update(status="ready", message="Piano pronto: controlla i tagli prima del rendering", overall=1.0)
    except ASRUnavailable as e:
        p.update(status="error", error=str(e), error_kind="asr_unavailable")
    except Exception as e:
        p.update(status="error", error=f"{type(e).__name__}: {e}", trace=traceback.format_exc()[-1500:])


def submit_render(p: Project, reel_ids: list[str], formats: list[str], quality: str) -> None:
    p.update(status="rendering", render={"progress": 0.0, "current": None, "state": "running"})
    POOL.submit(run_render, p, reel_ids, formats, quality)


def run_render(p: Project, reel_ids: list[str], formats: list[str], quality: str) -> None:
    try:
        plan = p.load_plan()
        jobs = [(r, e) for r in plan.reels if r.id in reel_ids for e in plan.exports if e.format_id in formats]
        outputs = [o for o in p.status()["outputs"] if not (o["reel_id"] in reel_ids and o["format_id"] in formats)]
        for i, (r, e) in enumerate(jobs):
            name = f"{r.id}_{e.format_id.replace(':', 'x')}_{quality}.mp4"
            cur = f"{r.id} · {e.format_id}"
            def prog(f: float, i=i, cur=cur) -> None:
                p.update(render={"progress": round((i + f) / len(jobs), 3), "current": cur, "state": "running"})
            render_reel(plan, r, e, p.out_dir / name, p.work_dir, quality, prog)
            outputs.append({"reel_id": r.id, "format_id": e.format_id, "quality": quality, "file": name,
                            "size": (p.out_dir / name).stat().st_size, "duration": r.duration,
                            "transcript": r.transcript, "caption": r.social.caption, "hashtags": r.social.hashtags,
                            "title": r.social.title})
            p.update(outputs=outputs)
        p.update(status="done", render={"progress": 1.0, "current": None, "state": "done"})
    except Exception as e:
        p.update(status="ready", render={"progress": 0.0, "current": None, "state": "error"},
                 error=f"Render fallito: {e}")
