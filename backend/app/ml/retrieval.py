from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import CollectionTrack, Track


async def search_collection(
    user_id: str,
    query_embedding: list[float],
    limit: int,
    db: AsyncSession,
) -> list[tuple[Track, float]]:
    """Search a user's collection by cosine similarity.

    Returns (Track, score) pairs ordered best-first; score is 0–1, higher is closer.
    """
    distance = Track.embedding.cosine_distance(query_embedding)

    result = await db.execute(
        select(Track, distance.label("distance"))
        .join(CollectionTrack, CollectionTrack.track_id == Track.id)
        .where(CollectionTrack.user_id == user_id)
        .where(Track.embedding.isnot(None))
        .order_by(distance)
        .limit(limit)
    )

    # invert distance to similarity; valid range is 0–1 for sentence-transformer embeddings
    return [(track, 1.0 - dist) for track, dist in result.all()]


def rerank_by_tags(
    results: list[tuple[Track, float]],
    keywords: list[str],
    limit: int,
    tag_weight: float = 0.3,
) -> list[tuple[Track, float]]:
    """Rerank cosine-similarity results by boosting tracks whose tags/genres overlap with keywords.

    Substring match (not exact) since Last.fm tags are free-form, e.g. keyword "workout"
    should match a track tagged "workout music". No-op if no keywords were extracted.
    """
    if not keywords:
        return results[:limit]

    keyword_set = {k.lower() for k in keywords}

    def tag_overlap(track: Track) -> float:
        track_terms = {t.lower() for t in (track.tags or []) + (track.genres or [])}
        if not track_terms:
            return 0.0
        matches = sum(
            1 for k in keyword_set if any(k in term or term in k for term in track_terms)
        )
        return matches / len(keyword_set)

    boosted = [
        (track, (1 - tag_weight) * cosine_score + tag_weight * tag_overlap(track))
        for track, cosine_score in results
    ]
    boosted.sort(key=lambda pair: pair[1], reverse=True)
    return boosted[:limit]
