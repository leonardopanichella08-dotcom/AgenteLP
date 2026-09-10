from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

# ─────────────────────────── Connections ───────────────────────────


class ConnectionCreate(BaseModel):
    account_type: str = Field(pattern="^(personal|company)$")
    display_name: str
    headline: str | None = None
    industry: str | None = None
    vanity_url: str | None = None
    raw_about: str | None = Field(
        default=None,
        description="Bio / esperienze / descrizione azienda incollate dal profilo LinkedIn.",
    )


class BrandProfileOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    mission: str
    value_proposition: str
    icp: str
    market_context: str
    tone_of_voice: str
    banned_phrases: list[str]
    goal: str
    generated_by_model: str | None = None


class ConnectionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    account_type: str
    display_name: str
    headline: str | None
    industry: str | None
    vanity_url: str | None
    status: str
    created_at: datetime
    brand_profile: BrandProfileOut | None = None
    documents_count: int = 0


# ─────────────────────────── Knowledge base ───────────────────────────


class KbDocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    filename: str
    mime_type: str
    size_bytes: int
    status: str
    created_at: datetime


# ─────────────────────────── Search ───────────────────────────


class SearchConfigIn(BaseModel):
    name: str = "Ricerca principale"
    niche: str
    keywords_primary: list[str] = []
    keywords_secondary: list[str] = []
    geo: str = Field(default="italy", pattern="^(world|europe|italy)$")


class SearchConfigOut(SearchConfigIn):
    model_config = ConfigDict(from_attributes=True)

    id: str
    is_active: bool


# ─────────────────────────── Tasks / discovery ───────────────────────────


class RunDiscoveryIn(BaseModel):
    connection_id: str
    niche: str
    keywords_primary: list[str] = []
    keywords_secondary: list[str] = []
    geo: str = Field(default="italy", pattern="^(world|europe|italy)$")
    limit: int = Field(default=10, ge=1, le=25)
    variants_per_post: int = Field(default=2, ge=1, le=3)


class GeneratedResponseOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    kind: str
    status: str
    execution_mode: str
    body: str
    repost_caption: str | None
    hook_type: str | None
    rationale: str | None
    model: str
    variant_index: int
    deeplink_url: str | None
    created_at: datetime


class DiscoveredPostOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    linkedin_post_url: str
    author_name: str
    author_headline: str | None
    author_profile_url: str | None
    niche: str | None
    text_excerpt: str
    posted_at: datetime | None
    views: int | None
    reactions: int
    comments: int
    reposts: int
    engagement_score: float
    rank: int | None
    data_source: str
    responses: list[GeneratedResponseOut] = []


class TaskOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    agent_key: str
    type: str
    status: str
    params: dict
    result_summary: dict | None
    error: str | None
    queued_at: datetime
    started_at: datetime | None
    finished_at: datetime | None


class TaskDetailOut(TaskOut):
    posts: list[DiscoveredPostOut] = []


class RegenerateIn(BaseModel):
    kind: str = Field(default="comment", pattern="^(comment|repost_with_comment)$")


class ManualPost(BaseModel):
    text: str = Field(min_length=20)
    author_name: str = "Autore del post"
    author_headline: str | None = None
    url: str | None = None
    reactions: int = 0
    comments: int = 0
    views: int | None = None


class AnalyzeIn(BaseModel):
    """Analisi di post incollati a mano (100% gratis, sempre accurata)."""

    connection_id: str
    niche: str = "Manuale"
    posts: list[ManualPost] = Field(min_length=1, max_length=10)
    variants_per_post: int = Field(default=2, ge=1, le=3)
