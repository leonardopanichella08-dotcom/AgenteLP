"""Unit test sui componenti dell'agente (nessuna rete)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.agent.discovery import DiscoveryQuery, SampleDiscoveryProvider
from app.agent.engine import _demo_generate
from app.agent.prompt import BrandContext, DiscoveredPost, build_system_blocks
from app.agent.ranking import engagement_score
from app.agent.retriever import LexicalRetriever, chunk_text


def _now_minus(days: int) -> datetime:
    return datetime.now(timezone.utc) - timedelta(days=days)


def test_engagement_score_rewards_comments_and_recency():
    fresh = engagement_score(views=10000, reactions=100, comments=100, reposts=0, posted_at=_now_minus(1))
    old = engagement_score(views=10000, reactions=100, comments=100, reposts=0, posted_at=_now_minus(30))
    assert fresh > old > 0

    talky = engagement_score(views=10000, reactions=0, comments=100, reposts=0, posted_at=_now_minus(1))
    likey = engagement_score(views=10000, reactions=100, comments=0, reposts=0, posted_at=_now_minus(1))
    assert talky > likey  # i commenti pesano di piu' delle reaction


def test_lexical_retriever_ranks_relevant_chunk_first():
    chunks = [
        "Ricetta della carbonara con guanciale e pecorino.",
        "La qualificazione degli account riduce il ciclo di vendita B2B.",
        "Storia dell'arte rinascimentale a Firenze.",
    ]
    r = LexicalRetriever(chunks)
    top = r.search("come accorciare il ciclo di vendita qualificando gli account", k=1)
    assert top and "qualificazione" in top[0]


def test_chunk_text_respects_size():
    text = "\n\n".join(f"Paragrafo {i} " + "parola " * 60 for i in range(10))
    chunks = chunk_text(text, size=500, overlap=80)
    assert chunks and all(len(c) <= 900 for c in chunks)


def test_sample_discovery_geo_widening():
    p = SampleDiscoveryProvider()
    base = dict(niche="AI B2B / Sales Intelligence",
               keywords_primary=["sales", "automation", "icp", "outbound"],
               keywords_secondary=["revops", "pipeline", "forecast"])
    it = p.discover(DiscoveryQuery(**base, geo="italy", limit=20))
    eu = p.discover(DiscoveryQuery(**base, geo="europe", limit=20))
    ww = p.discover(DiscoveryQuery(**base, geo="world", limit=20))
    assert 0 < len(it) <= len(eu) <= len(ww)
    assert all(a.score >= b.score for a, b in zip(ww, ww[1:]))


def test_demo_generate_shape_and_constraints():
    ctx = BrandContext(display_name="Marco", account_type="personal",
                       headline="Sales intelligence per team B2B",
                       value_proposition="Meno volume, piu' segnale.")
    post = DiscoveredPost(author_name="Elena Bianchi", niche="AI B2B",
                          url="https://linkedin.com/x", text="L'AI serve a qualificare, non a scrivere piu' email. Sbagliato pensare il contrario.",
                          reactions=100, comments=30)
    out = _demo_generate(ctx, post, n=3)["output"]
    assert out["skip"] is False
    assert len(out["comments"]) == 3
    for c in out["comments"]:
        assert c["hook_type"] in {"contrarian", "data_point", "story", "question", "reframe"}
        assert "#" not in c["body"]  # niente hashtag nei commenti
        assert 120 <= len(c["body"]) <= 900
    assert out["repost_with_comment"]["caption"]


def test_system_blocks_use_prompt_caching():
    ctx = BrandContext(display_name="X", account_type="company")
    blocks = build_system_blocks(ctx, ["snippet uno", "snippet due"])
    assert blocks[0]["cache_control"] == {"type": "ephemeral"}
    assert "snippet uno" in blocks[1]["text"]
