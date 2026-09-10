from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from ..andrea import docgen, engine
from ..db import get_db
from ..deps import get_or_create_user
from ..models import AndreaDocument, AndreaIteration, AndreaRun, SimulatorLaw
from ..schemas import AndreaRunIn, AndreaRunOut, LawOut
from ..services import extract_text

router = APIRouter(prefix="/api/andrea", tags=["andrea"])
_MAX_DOC_BYTES = 10 * 1024 * 1024


def _laws(db: Session) -> list[dict]:
    rows = db.scalars(select(SimulatorLaw).order_by(SimulatorLaw.created_at)).all()
    return [{"code": r.code, "module": r.module, "title": r.title, "body": r.body,
             "source": r.source} for r in rows]


def _detail(db: Session, run_id: str) -> AndreaRun:
    run = db.scalar(
        select(AndreaRun).where(AndreaRun.id == run_id)
        .options(selectinload(AndreaRun.iterations), selectinload(AndreaRun.documents))
    )
    if run is None:
        raise HTTPException(404, "Run non trovato")
    return run


def _full_context(run: AndreaRun) -> str:
    """input_text + testo estratto dai documenti allegati."""
    ctx = run.input_text
    for doc in run.documents:
        if doc.extracted_text.strip():
            ctx += (
                f"\n\n--- DOCUMENTO ALLEGATO: {doc.filename} ---\n"
                f"{doc.extracted_text[:12000]}"
            )
    return ctx


@router.get("/laws", response_model=list[LawOut])
def list_laws(db: Session = Depends(get_db)):
    return db.scalars(select(SimulatorLaw).order_by(SimulatorLaw.code)).all()


@router.get("/runs", response_model=list[AndreaRunOut])
def list_runs(db: Session = Depends(get_db)):
    user = get_or_create_user(db)
    return db.scalars(
        select(AndreaRun).where(AndreaRun.user_id == user.id)
        .options(selectinload(AndreaRun.iterations), selectinload(AndreaRun.documents))
        .order_by(AndreaRun.created_at.desc()).limit(30)
    ).all()


@router.post("/runs", response_model=AndreaRunOut, status_code=201)
def create_run(payload: AndreaRunIn, db: Session = Depends(get_db)):
    """Crea il run in bozza. Allega i documenti, poi avvia con /step."""
    user = get_or_create_user(db)
    run = AndreaRun(
        user_id=user.id,
        startup_name=payload.startup_name.strip(),
        input_text=payload.input_text.strip(),
        max_iterations=payload.max_iterations,
        status="draft",
    )
    db.add(run)
    db.commit()
    return _detail(db, run.id)


@router.post("/runs/{run_id}/documents", response_model=AndreaRunOut, status_code=201)
async def add_document(
    run_id: str, file: UploadFile = File(...), db: Session = Depends(get_db)
):
    run = _detail(db, run_id)
    if run.status not in ("draft", "running"):
        raise HTTPException(409, "Il run e' gia' concluso")
    data = await file.read()
    if len(data) > _MAX_DOC_BYTES:
        raise HTTPException(413, "File troppo grande (max 10 MB)")
    text = extract_text(file.filename or "documento", data, file.content_type or "")
    if not text.strip():
        raise HTTPException(422, "Nessun testo estraibile dal file")
    db.add(AndreaDocument(
        run_id=run.id,
        filename=file.filename or "documento",
        mime_type=file.content_type or "application/octet-stream",
        size_bytes=len(data),
        extracted_text=text,
    ))
    db.commit()
    return _detail(db, run.id)


@router.delete("/runs/{run_id}/documents/{doc_id}", status_code=204)
def delete_document(run_id: str, doc_id: str, db: Session = Depends(get_db)):
    doc = db.get(AndreaDocument, doc_id)
    if doc is not None and doc.run_id == run_id:
        db.delete(doc)
        db.commit()


@router.post("/runs/{run_id}/step", response_model=AndreaRunOut)
def step(run_id: str, db: Session = Depends(get_db)):
    run = _detail(db, run_id)

    # bozza -> costruisci la mappa sistemica (input + documenti) e avvia
    if run.status == "draft":
        try:
            out, model = engine.build_systemic_map(
                run.startup_name, _full_context(run), _laws(db)
            )
            run.systemic_map = out.get("map_md", "")
            run.lethal_flaws = out.get("lethal_flaws", [])
            run.model = model
            run.status = "running"
            db.commit()
        except Exception as exc:  # noqa: BLE001
            run.status = "failed"
            run.error = f"Mappa sistemica: {exc}"
            run.finished_at = datetime.utcnow()
            db.commit()
            raise HTTPException(502, run.error) from exc
        return _detail(db, run.id)

    if run.status != "running":
        return run
    idx = run.current_iteration + 1
    if idx > run.max_iterations:
        _finalize(db, run)
        return _detail(db, run.id)

    prev = run.iterations[-1].version_md if run.iterations else _full_context(run)
    prev_flaws = [it.lethal_flaw for it in run.iterations]
    try:
        out, model = engine.run_iteration(
            startup_name=run.startup_name,
            index=idx,
            total=run.max_iterations,
            prev_version=prev,
            systemic_map=run.systemic_map,
            lethal_flaws=run.lethal_flaws,
            laws=_laws(db),
            prev_flaws=prev_flaws,
        )
    except Exception as exc:  # noqa: BLE001
        run.status = "failed"
        run.error = f"Iterazione {idx}: {exc}"
        run.finished_at = datetime.utcnow()
        db.commit()
        raise HTTPException(502, run.error) from exc

    db.add(AndreaIteration(
        run_id=run.id,
        index=idx,
        lethal_flaw=out.get("lethal_flaw", ""),
        stress_test=out.get("stress_test", ""),
        research_notes=out.get("research_notes", ""),
        redesign_prompt=out.get("redesign_prompt", ""),
        version_md=out.get("version_md", ""),
        key_numbers=out.get("key_numbers", {}) or {},
        citations=out.get("citations", []) or [],
    ))
    run.current_iteration = idx
    run.model = model
    db.commit()

    run = _detail(db, run.id)
    if run.current_iteration >= run.max_iterations:
        _finalize(db, run)
        run = _detail(db, run.id)
    return run


def _finalize(db: Session, run: AndreaRun) -> None:
    if run.status != "running":
        return
    final_version = run.iterations[-1].version_md if run.iterations else run.input_text
    all_flaws = [it.lethal_flaw for it in run.iterations]
    try:
        out, model = engine.finalize(run.startup_name, final_version, all_flaws)
    except Exception as exc:  # noqa: BLE001
        run.status = "failed"
        run.error = f"Consolidamento finale: {exc}"
        run.finished_at = datetime.utcnow()
        db.commit()
        return

    run.final_report = out.get("report_md", "")
    run.narrative = out.get("narrative_md", "")
    run.assumptions = out.get("assumptions", {}) or {}
    run.model = model
    run.status = "succeeded"
    run.finished_at = datetime.utcnow()

    # cervello permanente: aggiungi le nuove leggi (dedupe per code)
    existing = set(db.scalars(select(SimulatorLaw.code)))
    for law in out.get("new_laws", []) or []:
        code = (law.get("code") or "").strip()
        if not code or code in existing:
            continue
        db.add(SimulatorLaw(
            code=code, module=law.get("module", "Varie"),
            title=law.get("title", ""), body=law.get("body", ""),
            source=law.get("source", f"[FONTE: {run.startup_name}, 2026]"),
        ))
        existing.add(code)
    db.commit()


@router.get("/runs/{run_id}", response_model=AndreaRunOut)
def get_run(run_id: str, db: Session = Depends(get_db)):
    return _detail(db, run_id)


@router.delete("/runs/{run_id}", status_code=204)
def delete_run(run_id: str, db: Session = Depends(get_db)):
    run = db.get(AndreaRun, run_id)
    if run is not None:
        db.delete(run)
        db.commit()


_ARTIFACTS = {
    "report_pdf": ("application/pdf", "Report_Strategico_{name}_VFINALE.pdf"),
    "narrative_pdf": ("application/pdf", "Analisi_Narrativa_PEF_{name}_VFINALE.pdf"),
    "financial_xlsx": (
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "Piano_Finanziario_{name}_VFINALE.xlsx",
    ),
}


@router.get("/runs/{run_id}/artifact/{kind}")
def artifact(run_id: str, kind: str, db: Session = Depends(get_db)):
    if kind not in _ARTIFACTS:
        raise HTTPException(404, "Artefatto sconosciuto")
    run = db.get(AndreaRun, run_id)
    if run is None or run.status != "succeeded":
        raise HTTPException(409, "Il run non e' ancora concluso")
    mime, name_tpl = _ARTIFACTS[kind]
    safe = "".join(c for c in run.startup_name if c.isalnum() or c in " -_").strip().replace(" ", "_")
    filename = name_tpl.format(name=safe or "startup")

    if kind == "financial_xlsx":
        data = docgen.build_xlsx(run.startup_name, run.assumptions or {})
    elif kind == "report_pdf":
        data = docgen.build_pdf(f"{run.startup_name} — Report Strategico V-FINALE", run.final_report)
    else:
        data = docgen.build_pdf(f"{run.startup_name} — Analisi Narrativa PEF", run.narrative)

    return Response(
        content=data,
        media_type=mime,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
