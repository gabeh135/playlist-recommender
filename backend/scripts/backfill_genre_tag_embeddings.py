"""backfill to populate genre_tag_embedding for tracks ingested before that column existed"""

import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.ml.encoders.embed import embed_text
from app.models import Track

BATCH_SIZE = 200


async def main():
    db_url = settings.active_database_url
    if db_url.startswith("postgresql://"):
        db_url = db_url.replace("postgresql://", "postgresql+asyncpg://", 1)
    engine = create_async_engine(db_url, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as db:
        result = await db.execute(select(Track).where(Track.genre_tag_embedding.is_(None)))
        tracks = result.scalars().all()
        print(f"{len(tracks)} tracks need genre_tag_embedding")

        for i, track in enumerate(tracks, start=1):
            genre_tag_input = f"Genres: {', '.join(track.genres or [])}. Tags: {', '.join(track.tags or [])}"
            track.genre_tag_embedding = embed_text(genre_tag_input)

            if i % BATCH_SIZE == 0:
                await db.commit()
                print(f"  → {i}/{len(tracks)} committed")

        await db.commit()
        print(f"Done — {len(tracks)} tracks backfilled")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
