"""Persistenza dei progetti su filesystem (trascrizioni, tracking, piano, output)."""
from __future__ import annotations

import json
import shutil
import threading
import time
import uuid
from pathlib import Path

import numpy as np

from . import reframe as rf
from .audio_analysis import compute_envelope
from .config import DATA_DIR, POLICIES
from .cutting import analyze_gaps
from .media import probe, read_audio
from .planner import SourceCtx
from .schemas import EditPlan
from .transcript import Transcript, lexical

_lock = threading.RLock()


class Project:
    def __init__(self, pid: str, root: Path | None = None):
        self.id = pid
        self.dir = (root or DATA_DIR / "projects") / pid
        self.src_dir, self.out_dir, self.work_dir = self.dir / "sources", self.dir / "out", self.dir / "work"
        self._ctx_cache: dict[str, SourceCtx] | None = None

    @classmethod
    def create(cls, meta: dict, root: Path | None = None) -> "Project":
        p = cls(uuid.uuid4().hex[:10], root)
        for d in (p.src_dir, p.out_dir, p.work_dir, p.dir / "transcripts", p.dir / "tracking"):
            d.mkdir(parents=True, exist_ok=True)
        p.write_status({"id": p.id, "created": time.time(), "status": "created", "message": "", "error": None,
                        "stages": {}, "overall": 0.0, "render": {"progress": 0.0, "current": None, "state": "idle"},
                        "outputs": [], **meta})
        return p

    def exists(self) -> bool:
        return (self.dir / "project.json").exists()

    def status(self) -> dict:
        with _lock:
            return json.loads((self.dir / "project.json").read_text())

    def write_status(self, st: dict) -> None:
        with _lock:
            tmp = self.dir / "project.json.tmp"
            tmp.write_text(json.dumps(st, ensure_ascii=False, indent=1))
            tmp.replace(self.dir / "project.json")

    def update(self, **kw) -> dict:
        with _lock:
            st = self.status(); st.update(kw); self.write_status(st); return st

    def update_stage(self, stage: str, frac: float, msg: str, order: list[tuple[str, str]]) -> None:
        with _lock:
            st = self.status()
            names = [k for k, _ in order]
            for k, label in order:
                s = st["stages"].setdefault(k, {"label": label, "progress": 0.0, "state": "pending"})
                i, cur = names.index(k), names.index(stage)
                if i < cur:
                    s["progress"], s["state"] = 1.0, "done"
                elif i == cur:
                    s["progress"], s["state"] = round(frac, 3), "running"
            st["message"] = msg
            st["overall"] = round((names.index(stage) + frac) / len(names), 3)
            self.write_status(st)

    # ── piano ────────────────────────────────────────────────────────────
    def save_plan(self, plan: EditPlan) -> None:
        (self.dir / "plan.json").write_text(plan.model_dump_json(indent=1))

    def load_plan(self) -> EditPlan:
        return EditPlan.model_validate_json((self.dir / "plan.json").read_text())

    def has_plan(self) -> bool:
        return (self.dir / "plan.json").exists()

    # ── contesto di analisi (per le modifiche manuali) ───────────────────
    def save_context(self, ctxs: dict[str, SourceCtx], transcripts: dict[str, Transcript]) -> None:
        for sid, c in ctxs.items():
            (self.dir / "transcripts" / f"{sid}.json").write_text(json.dumps(transcripts[sid].to_dict()))
            if c.tracking is not None:
                tr = c.tracking
                (self.dir / "tracking" / f"{sid}.json").write_text(json.dumps({
                    "width": tr.width, "height": tr.height, "coverage": tr.coverage, "sample_times": tr.sample_times,
                    "speaker_map": c.speaker_map, "speech": c.speech,
                    "tracks": [{"id": t.id, "t": t.t, "box": [list(b) for b in t.box], "mouth": t.mouth} for t in tr.tracks]}))
        self._ctx_cache = ctxs

    def load_context(self, plan: EditPlan) -> dict[str, SourceCtx]:
        if self._ctx_cache is not None:
            return self._ctx_cache
        pol = POLICIES[plan.cut_policy]
        out: dict[str, SourceCtx] = {}
        for s in plan.sources:
            tr = Transcript.from_dict(json.loads((self.dir / "transcripts" / f"{s.id}.json").read_text()), s.id)
            lex = lexical(tr.words)
            env = compute_envelope(read_audio(s.path, 16000), 16000)
            c = SourceCtx(s.id, probe(s.path), lex, env, analyze_gaps(lex, env, pol))
            tp = self.dir / "tracking" / f"{s.id}.json"
            if tp.exists():
                j = json.loads(tp.read_text())
                c.tracking = rf.TrackingResult(
                    [rf.Track(t["id"], t["t"], [tuple(b) for b in t["box"]], t["mouth"]) for t in j["tracks"]],
                    j["sample_times"], j["coverage"], j["width"], j["height"])
                c.speaker_map = {k: int(v) for k, v in j["speaker_map"].items()}
                c.speech = [tuple(x) for x in j["speech"]]
            out[s.id] = c
        self._ctx_cache = out
        return out

    def delete(self) -> None:
        shutil.rmtree(self.dir, ignore_errors=True)


def list_projects(root: Path | None = None) -> list[dict]:
    base = root or DATA_DIR / "projects"
    out = []
    if base.exists():
        for d in sorted(base.iterdir(), key=lambda p: -p.stat().st_mtime):
            if (d / "project.json").exists():
                st = json.loads((d / "project.json").read_text())
                out.append({k: st.get(k) for k in ("id", "mode", "status", "created", "formats")})
    return out


def waveform_peaks(path: str, points: int = 1500) -> list[float]:
    x = np.abs(read_audio(path, 8000))
    n = max(1, len(x) // points)
    pk = x[: n * points].reshape(-1, n).max(axis=1) if len(x) >= n * points else x
    m = pk.max() or 1.0
    return [round(float(v / m), 3) for v in pk]
