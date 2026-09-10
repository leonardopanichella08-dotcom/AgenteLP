from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def _uid() -> str:
    return uuid4().hex


def _now() -> datetime:
    return datetime.utcnow()


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uid)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    full_name: Mapped[str | None] = mapped_column(String(255))
    locale: Mapped[str] = mapped_column(String(8), default="it")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    connections: Mapped[list[LinkedInConnection]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class LinkedInConnection(Base):
    __tablename__ = "linkedin_connections"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    account_type: Mapped[str] = mapped_column(String(16))  # "personal" | "company"
    display_name: Mapped[str] = mapped_column(String(255))
    headline: Mapped[str | None] = mapped_column(String(400))
    industry: Mapped[str | None] = mapped_column(String(120))
    vanity_url: Mapped[str | None] = mapped_column(String(400))
    avatar_url: Mapped[str | None] = mapped_column(String(600))
    raw_about: Mapped[str | None] = mapped_column(Text)  # bio/esperienze incollate
    # Identità LinkedIn (valorizzata dall'OAuth; null per le connessioni manuali)
    linkedin_urn: Mapped[str | None] = mapped_column(String(255), index=True)
    auth_method: Mapped[str] = mapped_column(String(16), default="manual")  # manual|oauth
    status: Mapped[str] = mapped_column(String(16), default="active")
    # Token OAuth cifrato a riposo (Fernet)
    access_token_enc: Mapped[str | None] = mapped_column(Text)
    scopes: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    user: Mapped[User] = relationship(back_populates="connections")
    documents: Mapped[list[KbDocument]] = relationship(
        back_populates="connection", cascade="all, delete-orphan"
    )
    brand_profile: Mapped[BrandProfile | None] = relationship(
        back_populates="connection", cascade="all, delete-orphan", uselist=False
    )
    search_configs: Mapped[list[SearchConfig]] = relationship(
        back_populates="connection", cascade="all, delete-orphan"
    )


class KbDocument(Base):
    __tablename__ = "kb_documents"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uid)
    connection_id: Mapped[str] = mapped_column(
        ForeignKey("linkedin_connections.id", ondelete="CASCADE"), index=True
    )
    filename: Mapped[str] = mapped_column(String(400))
    mime_type: Mapped[str] = mapped_column(String(120))
    size_bytes: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(16), default="indexed")
    error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    connection: Mapped[LinkedInConnection] = relationship(back_populates="documents")
    chunks: Mapped[list[KbChunk]] = relationship(
        back_populates="document", cascade="all, delete-orphan"
    )


class KbChunk(Base):
    __tablename__ = "kb_chunks"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uid)
    document_id: Mapped[str] = mapped_column(
        ForeignKey("kb_documents.id", ondelete="CASCADE"), index=True
    )
    connection_id: Mapped[str] = mapped_column(String(32), index=True)
    chunk_index: Mapped[int] = mapped_column(Integer)
    content: Mapped[str] = mapped_column(Text)
    # Embedding opzionale (JSON list[float]); il retriever di default è lessicale.
    embedding: Mapped[list | None] = mapped_column(JSON)

    document: Mapped[KbDocument] = relationship(back_populates="chunks")


class BrandProfile(Base):
    __tablename__ = "brand_profiles"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uid)
    connection_id: Mapped[str] = mapped_column(
        ForeignKey("linkedin_connections.id", ondelete="CASCADE"), unique=True, index=True
    )
    mission: Mapped[str] = mapped_column(Text, default="")
    value_proposition: Mapped[str] = mapped_column(Text, default="")
    icp: Mapped[str] = mapped_column(Text, default="")
    market_context: Mapped[str] = mapped_column(Text, default="")
    tone_of_voice: Mapped[str] = mapped_column(
        Text, default="autorevole, diretto, concreto, zero buzzword"
    )
    # Nicchia + keyword derivate dall'analisi del profilo (pre-compilano la ricerca)
    niche: Mapped[str] = mapped_column(Text, default="")
    keywords_primary: Mapped[list] = mapped_column(JSON, default=list)
    keywords_secondary: Mapped[list] = mapped_column(JSON, default=list)
    banned_phrases: Mapped[list] = mapped_column(JSON, default=list)
    goal: Mapped[str] = mapped_column(
        Text, default="Generare conversazione e traffico qualificato verso il profilo"
    )
    generated_by_model: Mapped[str | None] = mapped_column(String(64))
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_now, onupdate=_now)

    connection: Mapped[LinkedInConnection] = relationship(back_populates="brand_profile")


class SearchConfig(Base):
    __tablename__ = "search_configs"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uid)
    connection_id: Mapped[str] = mapped_column(
        ForeignKey("linkedin_connections.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(200))
    niche: Mapped[str] = mapped_column(String(200))
    keywords_primary: Mapped[list] = mapped_column(JSON, default=list)
    keywords_secondary: Mapped[list] = mapped_column(JSON, default=list)
    geo: Mapped[str] = mapped_column(String(16), default="italy")  # world|europe|italy
    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    connection: Mapped[LinkedInConnection] = relationship(back_populates="search_configs")


class AgentTask(Base):
    __tablename__ = "agent_tasks"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uid)
    agent_key: Mapped[str] = mapped_column(String(32), default="luka")
    user_id: Mapped[str] = mapped_column(String(32), index=True)
    connection_id: Mapped[str] = mapped_column(String(32), index=True)
    type: Mapped[str] = mapped_column(String(24))  # discovery|generation|full_cycle
    status: Mapped[str] = mapped_column(String(16), default="queued")
    params: Mapped[dict] = mapped_column(JSON, default=dict)
    result_summary: Mapped[dict | None] = mapped_column(JSON)
    error: Mapped[str | None] = mapped_column(Text)
    queued_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    started_at: Mapped[datetime | None] = mapped_column(DateTime)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime)

    posts: Mapped[list[DiscoveredPost]] = relationship(
        back_populates="task", cascade="all, delete-orphan"
    )


class DiscoveredPost(Base):
    __tablename__ = "discovered_posts"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uid)
    task_id: Mapped[str] = mapped_column(
        ForeignKey("agent_tasks.id", ondelete="CASCADE"), index=True
    )
    connection_id: Mapped[str] = mapped_column(String(32), index=True)
    linkedin_post_url: Mapped[str] = mapped_column(String(600))
    author_name: Mapped[str] = mapped_column(String(255))
    author_headline: Mapped[str | None] = mapped_column(String(400))
    author_profile_url: Mapped[str | None] = mapped_column(String(600))
    niche: Mapped[str | None] = mapped_column(String(200))
    text_excerpt: Mapped[str] = mapped_column(Text)
    posted_at: Mapped[datetime | None] = mapped_column(DateTime)
    views: Mapped[int | None] = mapped_column(Integer)
    reactions: Mapped[int] = mapped_column(Integer, default=0)
    comments: Mapped[int] = mapped_column(Integer, default=0)
    reposts: Mapped[int] = mapped_column(Integer, default=0)
    engagement_score: Mapped[float] = mapped_column(Float, default=0.0)
    rank: Mapped[int | None] = mapped_column(Integer)
    data_source: Mapped[str] = mapped_column(String(32), default="sample")
    discovered_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    task: Mapped[AgentTask] = relationship(back_populates="posts")
    responses: Mapped[list[GeneratedResponse]] = relationship(
        back_populates="post", cascade="all, delete-orphan"
    )


class GeneratedResponse(Base):
    __tablename__ = "generated_responses"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uid)
    post_id: Mapped[str] = mapped_column(
        ForeignKey("discovered_posts.id", ondelete="CASCADE"), index=True
    )
    connection_id: Mapped[str] = mapped_column(String(32), index=True)
    kind: Mapped[str] = mapped_column(String(24))  # comment | repost_with_comment
    status: Mapped[str] = mapped_column(String(16), default="draft")
    execution_mode: Mapped[str] = mapped_column(String(24), default="assisted_deeplink")
    body: Mapped[str] = mapped_column(Text)
    repost_caption: Mapped[str | None] = mapped_column(Text)
    hook_type: Mapped[str | None] = mapped_column(String(32))
    rationale: Mapped[str | None] = mapped_column(Text)
    model: Mapped[str] = mapped_column(String(64), default="demo")
    prompt_version: Mapped[str | None] = mapped_column(String(64))
    tokens_input: Mapped[int | None] = mapped_column(Integer)
    tokens_output: Mapped[int | None] = mapped_column(Integer)
    variant_index: Mapped[int] = mapped_column(Integer, default=0)
    deeplink_url: Mapped[str | None] = mapped_column(String(600))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    post: Mapped[DiscoveredPost] = relationship(back_populates="responses")
