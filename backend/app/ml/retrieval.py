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
    distance = Track.genre_tag_embedding.cosine_distance(query_embedding)

    result = await db.execute(
        select(Track, distance.label("distance"))
        .join(CollectionTrack, CollectionTrack.track_id == Track.id)
        .where(CollectionTrack.user_id == user_id)
        .where(Track.genre_tag_embedding.isnot(None))
        .order_by(distance)
        .limit(limit)
    )

    # invert distance to similarity; valid range is 0–1 for sentence-transformer embeddings
    return [(track, 1.0 - dist) for track, dist in result.all()]
