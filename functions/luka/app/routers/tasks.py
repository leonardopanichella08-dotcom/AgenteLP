from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from ..agent.discovery import DiscoveryQuery, get_provider
from ..agent.engine import generate_engagement
from ..agent.prompt import BrandContext, DiscoveredPost as PromptPost
from ..db import get_db
from ..deps import build_deeplink, get_or_create_user
from ..kb_index import connection_chunks
from ..models import (
    AgentTask,
    BrandProfile,
    DiscoveredPost,
    GeneratedResponse,
    LinkedInConnection,
)
from ..schemas import RegenerateIn, RunDiscoveryIn, TaskDetailOut, TaskOut

router = APIRouter(prefix="/api/tasks", tags=["tasks"])


def _brand_context(conn: LinkedInConnection, bp: BrandProfile | None) -> BrandContext:
    return BrandContext(
        display_name=conn.display_name,
        account_type=conn.account_type,
        headline=conn.headline,
        industry=conn.industry,
        mission=bp.mission if bp else "",
        value_proposition=bp.value_proposition if bp else "",
        icp=bp.icp if bp else "",
        market_context=bp.market_context if bp else "",
        tone_of_voice=bp.tone_of_voice if bp else "autorevole, diretto, concreto",
        banned_phrases=list(bp.banned_phrases) if bp and bp.banned_phrases else [],
        goal=bp.goal if bp else "Generare conversazione e traffico verso il profilo",
    )


def _persist_responses(
    db: Session,
    post_row: DiscoveredPost,
    connection_id: str,
    result: dict,
) -> None:
    output = result.get("output", {})
    if output.get("skip"):
        return
    deeplink = build_deeplink(post_row.linkedin_post_url)

    for idx, c in enumerate(output.get("comments", [])):
        db.add(
            GeneratedResponse(
                post_id=post_row.id,
                connection_id=connection_id,
                kind="comment",
                status="draft",
                execution_mode="assisted_deeplink",
                body=c.get("body", "").strip(),
                hook_type=c.get("hook_type"),
                rationale=c.get("rationale"),
                model=result.get("model", "demo"),
                prompt_version=result.get("prompt_version"),
                tokens_input=result.get("tokens_input"),
                tokens_output=result.get("tokens_output"),
                variant_index=idx,
                deeplink_url=deeplink,
            )
        )

    repost = output.get("repost_with_comment")
    if repost and repost.get("caption"):
        db.add(
            GeneratedResponse(
                post_id=post_row.id,
                connection_id=connection_id,
                kind="repost_with_comment",
                status="draft",
                execution_mode="assisted_deeplink",
                body=repost["caption"].strip(),
                repost_caption=repost["caption"].strip(),
                hook_type=repost.get("hook_type"),
                rationale=repost.get("rationale"),
                model=result.get("model", "demo"),
                prompt_version=result.get("prompt_version"),
                variant_index=0,
                deeplink_url=deeplink,
            )
        )


@router.post("/discovery", response_model=TaskDetailOut, status_code=201)
def run_discovery(payload: RunDiscoveryIn, db: Session = Depends(get_db)):
    user = get_or_create_user(db)
    conn = db.get(LinkedInConnection, payload.connection_id)
    if conn is None:
        raise HTTPException(404, "Connessione non trovata")

    task = AgentTask(
        agent_key="luka",
        user_id=user.id,
        connection_id=conn.id,
        type="full_cycle",
        status="running",
        params=payload.model_dump(),
        started_at=datetime.utcnow(),
    )
    db.add(task)
    db.commit()
    db.refresh(task)

    try:
        provider = get_provider()
        raw_posts = provider.discover(
            DiscoveryQuery(
                niche=payload.niche,
                keywords_primary=payload.keywords_primary,
                keywords_secondary=payload.keywords_secondary,
                geo=payload.geo,
                limit=payload.limit,
            )
        )

        bp = conn.brand_profile
        ctx = _brand_context(conn, bp)
        generated_count = 0

        for rank, rp in enumerate(raw_posts, start=1):
            post_row = DiscoveredPost(
                task_id=task.id,
                connection_id=conn.id,
                linkedin_post_url=rp.url,
                author_name=rp.author_name,
                author_headline=rp.author_headline,
                author_profile_url=rp.author_profile_url,
                niche=rp.niche,
                text_excerpt=rp.text,
                posted_at=rp.posted_at,
                views=rp.views,
                reactions=rp.reactions,
                comments=rp.comments,
                reposts=rp.reposts,
                engagement_score=rp.score,
                rank=rank,
                data_source=rp.data_source,
            )
            db.add(post_row)
            db.flush()

            snippets = connection_chunks(db, conn.id, query=rp.text, k=4)
            result = generate_engagement(
                ctx,
                PromptPost(
                    author_name=rp.author_name,
                    author_headline=rp.author_headline,
                    niche=rp.niche or payload.niche,
                    url=rp.url,
                    text=rp.text,
                    reactions=rp.reactions,
                    comments=rp.comments,
                    views=rp.views,
                    engagement_score=rp.score,
                ),
                rag_snippets=snippets,
                n_comment_variants=payload.variants_per_post,
            )
            _persist_responses(db, post_row, conn.id, result)
            generated_count += len(result.get("output", {}).get("comments", []))

        task.status = "succeeded"
        task.finished_at = datetime.utcnow()
        task.result_summary = {
            "discovered": len(raw_posts),
            "comments_generated": generated_count,
            "provider": provider.name,
            "mode": "llm" if raw_posts and _brand_has_llm() else "demo",
        }
        db.add(task)
        db.commit()
    except Exception as exc:  # noqa: BLE001
        task.status = "failed"
        task.error = str(exc)
        task.finished_at = datetime.utcnow()
        db.add(task)
        db.commit()
        raise HTTPException(500, f"Discovery fallita: {exc}") from exc

    return _task_detail(db, task.id)


def _brand_has_llm() -> bool:
    from ..config import get_settings

    return get_settings().has_llm


@router.get("", response_model=list[TaskOut])
def list_tasks(db: Session = Depends(get_db)):
    user = get_or_create_user(db)
    rows = db.scalars(
        select(AgentTask)
        .where(AgentTask.user_id == user.id)
        .order_by(AgentTask.queued_at.desc())
        .limit(50)
    ).all()
    return rows


@router.get("/{task_id}", response_model=TaskDetailOut)
def get_task(task_id: str, db: Session = Depends(get_db)):
    return _task_detail(db, task_id)


def _task_detail(db: Session, task_id: str) -> AgentTask:
    task = db.scalar(
        select(AgentTask)
        .where(AgentTask.id == task_id)
        .options(
            selectinload(AgentTask.posts).selectinload(DiscoveredPost.responses)
        )
    )
    if task is None:
        raise HTTPException(404, "Task non trovato")
    task.posts.sort(key=lambda p: p.rank or 999)
    for p in task.posts:
        p.responses.sort(key=lambda r: (r.kind != "comment", r.variant_index))
    return task


@router.post("/posts/{post_id}/regenerate", response_model=TaskDetailOut)
def regenerate(post_id: str, payload: RegenerateIn, db: Session = Depends(get_db)):
    post_row = db.get(DiscoveredPost, post_id)
    if post_row is None:
        raise HTTPException(404, "Post non trovato")
    conn = db.get(LinkedInConnection, post_row.connection_id)
    ctx = _brand_context(conn, conn.brand_profile if conn else None)

    # Rigenera l'intero set di risposte per il post (comportamento prevedibile).
    for r in list(post_row.responses):
        db.delete(r)
    db.flush()

    snippets = connection_chunks(db, post_row.connection_id, query=post_row.text_excerpt, k=4)
    result = generate_engagement(
        ctx,
        PromptPost(
            author_name=post_row.author_name,
            author_headline=post_row.author_headline,
            niche=post_row.niche or "",
            url=post_row.linkedin_post_url,
            text=post_row.text_excerpt,
            reactions=post_row.reactions,
            comments=post_row.comments,
            views=post_row.views,
            engagement_score=post_row.engagement_score,
        ),
        rag_snippets=snippets,
        n_comment_variants=2,
    )
    _persist_responses(db, post_row, post_row.connection_id, result)
    db.commit()
    return _task_detail(db, post_row.task_id)
