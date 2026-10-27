"""API REELS — agente di video editing autonomo (FastAPI)."""
from __future__ import annotations

import json
import re
import shutil
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import jobs
from .config import FORMATS, POLICIES
from .edit import EditError, apply_ops
from .llm import system_prompt
from .schemas import json_schema
from .store import Project, list_projects, waveform_peaks

STATIC = Path(__file__).parent / "static"

app = FastAPI(title="REELS API", version="0.1.0",
              description="Agente di video editing: script+clip → video montato, video lungo → reel.")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


def _project(pid: str) -> Project:
    if not re.fullmatch(r"[a-f0-9]{10}", pid):
        raise HTTPException(404, "progetto inesistente")
    p = Project(pid)
    if not p.exists():
        raise HTTPException(404, "progetto inesistente")
    return p


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/api/meta")
def meta():
    return {"function": "reels", "capabilities": ["script_assembly", "long_form_extraction", "multi_format_export"],
            "modes": ["script_assembly", "long_form_extraction"], "cut_policies": list(POLICIES)}


@app.get("/api/formats")
def formats():
    return [{"id": f.id, "width": f.width, "height": f.height, "platforms": list(f.platforms)} for f in FORMATS.values()]


@app.get("/api/schema")
def schema():
    return json_schema()


@app.get("/api/system-prompt")
def get_system_prompt():
    return {"markdown": system_prompt()}


@app.get("/api/projects")
def projects():
    return list_projects()


@app.post("/api/projects")
async def create_project(
    mode: str = Form(...), formats: str = Form("9:16"), script: str = Form(""), cut_policy: str = Form("natural"),
    reframe: str = Form("auto"), subtitle_preset: str = Form("hormozi"), n_min: int = Form(3), n_max: int = Form(5),
    min_dur: float = Form(15), max_dur: float = Form(60), fps: int = Form(30), language: str = Form("it"),
    sfx: bool = Form(True), emoji: bool = Form(True), zoom: bool = Form(True), broll: bool = Form(False),
    files: list[UploadFile] = File(...),
):
    if mode not in ("script_assembly", "long_form_extraction"):
        raise HTTPException(422, "mode non valido")
    fmts = [f for f in formats.split(",") if f]
    if not fmts or any(f not in FORMATS for f in fmts):
        raise HTTPException(422, f"formati validi: {list(FORMATS)}")
    if cut_policy not in POLICIES:
        raise HTTPException(422, "cut_policy non valida")
    if mode == "script_assembly" and not script.strip():
        raise HTTPException(422, "la modalità script richiede il testo dello script")
    videos = [f for f in files if (f.filename or "").lower().endswith((".mp4", ".mov", ".mkv", ".webm", ".m4v", ".avi"))]
    if not videos:
        raise HTTPException(422, "carica almeno un file video")
    opts = {"mode": mode, "formats": fmts, "cut_policy": cut_policy, "reframe": reframe, "subtitle_preset": subtitle_preset,
            "n_min": n_min, "n_max": n_max, "min_dur": min_dur, "max_dur": max_dur, "fps": fps, "language": language,
            "sfx": sfx, "emoji": emoji, "zoom": zoom, "broll": broll, "script": script if mode == "script_assembly" else None}
    p = Project.create({"mode": mode, "formats": fmts, "options": opts, "sources": []})
    sources = []
    for k, f in enumerate(files):
        name = re.sub(r"[^\w.\-]", "_", Path(f.filename or f"file{k}").name)
        with open(p.src_dir / name, "wb") as out:
            shutil.copyfileobj(f.file, out)
        if name.lower().endswith(".json"):
            continue
        sources.append({"id": f"clip{len(sources) + 1}" if mode == "script_assembly" else f"video{len(sources) + 1}",
                        "filename": name, "label": Path(name).stem})
    p.update(sources=sources)
    jobs.submit_analysis(p)
    return {"id": p.id}


class DemoReq(BaseModel):
    mode: str = "long_form_extraction"
    formats: list[str] = ["9:16"]


@app.post("/api/demo")
def demo(req: DemoReq):
    """Progetto di prova con media sintetici e verità-terreno nota (nessuna chiave ASR necessaria)."""
    from . import demo as d
    fmts = [f for f in req.formats if f in FORMATS] or ["9:16"]
    if req.mode == "script_assembly":
        opts = {"mode": req.mode, "formats": fmts, "script": d.SCRIPT_TEXT, "min_dur": 3, "max_dur": 60}
    else:
        opts = {"mode": "long_form_extraction", "formats": fmts, "n_min": 1, "n_max": 3, "min_dur": 8, "max_dur": 40}
    p = Project.create({"mode": opts["mode"], "formats": fmts, "options": opts, "sources": [], "demo": True})
    sources, faces = [], None
    if req.mode == "script_assembly":
        pr = d.make_script_project(p.src_dir)
        for cid, v in pr["clips"].items():
            (p.src_dir / f"{cid}.transcript.json").write_text(json.dumps(v["transcript"].to_dict()))
            sources.append({"id": cid, "filename": f"{cid}.mp4", "label": cid})
    else:
        pr = d.make_podcast(p.src_dir)
        (p.src_dir / "podcast.transcript.json").write_text(json.dumps(pr["transcript"].to_dict()))
        sources.append({"id": "podcast", "filename": "podcast.mp4", "label": "podcast (demo)"})
        faces = [list(b) for b in pr["faces"].values()]
    p.update(sources=sources, demo_faces=faces)
    jobs.submit_analysis(p)
    return {"id": p.id}


@app.get("/api/projects/{pid}")
def project_status(pid: str):
    return _project(pid).status()


@app.delete("/api/projects/{pid}")
def delete_project(pid: str):
    _project(pid).delete()
    return {"ok": True}


@app.get("/api/projects/{pid}/plan")
def get_plan(pid: str):
    p = _project(pid)
    if not p.has_plan():
        raise HTTPException(409, "piano non ancora pronto")
    return json.loads(p.load_plan().model_dump_json())


class EditReq(BaseModel):
    reel_id: str
    ops: list[dict]


@app.post("/api/projects/{pid}/edit")
def edit(pid: str, req: EditReq):
    p = _project(pid)
    if not p.has_plan():
        raise HTTPException(409, "piano non ancora pronto")
    plan = p.load_plan()
    try:
        plan = apply_ops(plan, req.reel_id, req.ops, p.load_context(plan))
    except EditError as e:
        raise HTTPException(422, str(e))
    p.save_plan(plan)
    return json.loads(plan.model_dump_json())


class RenderReq(BaseModel):
    reels: list[str] | None = None
    formats: list[str] | None = None
    quality: str = "final"


@app.post("/api/projects/{pid}/render")
def render(pid: str, req: RenderReq):
    p = _project(pid)
    if not p.has_plan():
        raise HTTPException(409, "piano non ancora pronto")
    if p.status()["status"] == "rendering":
        raise HTTPException(409, "render già in corso")
    plan = p.load_plan()
    reels = req.reels or [r.id for r in plan.reels if r.selected]
    fmts = req.formats or [e.format_id for e in plan.exports]
    if not reels:
        raise HTTPException(422, "nessun reel selezionato")
    if req.quality not in ("draft", "final"):
        raise HTTPException(422, "quality: draft|final")
    jobs.submit_render(p, reels, fmts, req.quality)
    return {"ok": True, "reels": reels, "formats": fmts}


@app.get("/api/projects/{pid}/files/{name}")
def download(pid: str, name: str):
    p = _project(pid)
    f = p.out_dir / Path(name).name
    if not f.exists():
        raise HTTPException(404)
    return FileResponse(f, media_type="video/mp4", filename=f.name)


@app.get("/api/projects/{pid}/media/{source_id}")
def media(pid: str, source_id: str):
    p = _project(pid)
    st = p.status()
    s = next((x for x in st["sources"] if x["id"] == source_id), None)
    if not s:
        raise HTTPException(404)
    return FileResponse(p.src_dir / s["filename"])      # Range gestito da Starlette: scrubbing nel player


@app.get("/api/projects/{pid}/waveform/{source_id}")
def waveform(pid: str, source_id: str, points: int = 1500):
    p = _project(pid)
    s = next((x for x in p.status()["sources"] if x["id"] == source_id), None)
    if not s:
        raise HTTPException(404)
    cache = p.work_dir / f"wf_{source_id}_{points}.json"
    if cache.exists():
        return json.loads(cache.read_text())
    out = {"peaks": waveform_peaks(str(p.src_dir / s["filename"]), min(max(points, 100), 4000))}
    cache.write_text(json.dumps(out))
    return out


app.mount("/", StaticFiles(directory=STATIC, html=True), name="static")
