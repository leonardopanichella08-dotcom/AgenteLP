from __future__ import annotations

import math
from datetime import datetime, timezone


def engagement_score(
    *,
    views: int | None,
    reactions: int,
    comments: int,
    reposts: int,
    posted_at: datetime | None,
    half_life_days: float = 7.0,
) -> float:
    """Punteggio di viralità: engagement rate ponderato x recency x reach.

    - commenti e repost pesano più delle reaction (segnale di conversazione)
    - decadimento temporale: ~metà peso ogni `half_life_days` (7 per LinkedIn,
      più alto per fonti a ciclo lento come Hacker News)
    - log10(views) per non far esplodere i post enormi
    """
    v = max(views or 0, 1)
    weighted = reactions + 3 * (comments or 0) + 5 * (reposts or 0)
    engagement_rate = weighted / v

    if posted_at is not None:
        if posted_at.tzinfo is None:
            posted_at = posted_at.replace(tzinfo=timezone.utc)
        age_days = (datetime.now(timezone.utc) - posted_at).total_seconds() / 86400
        recency = math.exp(-max(age_days, 0) / max(half_life_days, 0.5))
    else:
        recency = 0.5

    reach = math.log10(v)
    return round(engagement_rate * 100 * recency * reach, 4)
