"""script to seed the demo user's collection with ~1000 tracks from LastFM charts"""

import asyncio
import os
import sys
import time
from datetime import datetime, timezone
from uuid import uuid4

import httpx

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.ml.encoders.embed import embed_text
from app.models import Base, CollectionSource, CollectionTrack, Track, User
from app.services.lastfm_client import LastFmClient
from app.services.spotify_client import SpotifyClient

TARGET = 1000
LASTFM_PAGE_SIZE = 50
SPOTIFY_SEARCH_DELAY = 0.1

def get_lastfm_top_tracks(api_key: str, target: int) -> list[dict]:
    """Fetch top tracks from Last.fm charts across multiple pages."""
    client = httpx.Client()
    tracks = []
    page = 1

    while len(tracks) < target:
        resp = client.get(
            "http://ws.audioscrobbler.com/2.0/",
            params={
                "method": "chart.getTopTracks",
                "limit": LASTFM_PAGE_SIZE,
                "page": page,
                "api_key": api_key,
                "format": "json",
            },
        ).json()

        raw = resp.get("tracks", {}).get("track", [])
        if not raw:
            break

        for t in raw:
            tracks.append({
                "title": t["name"],
                "artist": t["artist"]["name"],
            })

        total_pages = int(resp.get("tracks", {}).get("@attr", {}).get("totalPages", 1))
        print(f"  Last.fm page {page}/{min(total_pages, (target // LASTFM_PAGE_SIZE) + 1)} — {len(tracks)} tracks so far")

        if page >= total_pages:
            break
        page += 1

    return tracks[:target]


async def main():
    db_url = settings.active_database_url
    if db_url.startswith("postgresql://"):
        db_url = db_url.replace("postgresql://", "postgresql+asyncpg://", 1)
    engine = create_async_engine(db_url, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    spotify = SpotifyClient()
    lastfm = LastFmClient()

    async with async_session() as db:
        # Resolve or create demo user
        demo_user_id = settings.demo_user_id
        if demo_user_id:
            result = await db.execute(select(User).where(User.id == demo_user_id))
            demo_user = result.scalar_one_or_none()
            if not demo_user:
                print(f"ERROR: DEMO_USER_ID {demo_user_id} not found in database")
                return
            print(f"Using existing demo user: {demo_user_id}")
        else:
            demo_user = User(id=str(uuid4()))
            db.add(demo_user)
            await db.commit()
            await db.refresh(demo_user)
            demo_user_id = str(demo_user.id)
            print(f"\nCreated demo user. Save this as DEMO_USER_ID:\n  {demo_user_id}\n")

        # Fetch target list from Last.fm
        print(f"\nFetching {TARGET} top tracks from Last.fm...")
        candidates = get_lastfm_top_tracks(settings.lastfm_api_key, TARGET)
        print(f"Got {len(candidates)} candidates\n")

        added = 0
        skipped = 0

        for i, candidate in enumerate(candidates, 1):
            title = candidate["title"]
            artist = candidate["artist"]
            print(f"[{i}/{len(candidates)}] {title} — {artist}")

            # Search Spotify for this track
            try:
                results = spotify.search_tracks(f"{artist} {title}", limit=1)
            except Exception as e:
                print(f"  Spotify search failed: {e} — skipping")
                skipped += 1
                continue

            if not results:
                print("  Not found on Spotify — skipping")
                skipped += 1
                continue

            raw = results[0]
            spotify_id = raw["id"]

            # Check if track already in DB
            existing = await db.execute(select(Track).where(Track.spotify_id == spotify_id))
            track = existing.scalar_one_or_none()

            if track is None:
                artist_id = raw["artists"][0]["id"]
                artist_name = raw["artists"][0]["name"]
                track_title = raw["name"]
                album = raw.get("album", {}).get("name", "")

                release_year = None
                rd = raw.get("album", {}).get("release_date", "")
                if rd:
                    try:
                        release_year = int(rd[:4])
                    except ValueError:
                        pass

                images = raw.get("album", {}).get("images", [])
                album_art_url = images[0]["url"] if images else None

                genre_map = spotify.get_artist_genres([artist_id])
                genres = genre_map.get(artist_id, [])
                tags = lastfm.get_track_tags(artist_name, track_title)

                embedding_input = f"{track_title} by {artist_name}. Genres: {', '.join(genres)}. Tags: {', '.join(tags)}"
                embedding = embed_text(embedding_input)

                track = Track(
                    spotify_id=spotify_id,
                    title=track_title,
                    artist=artist_name,
                    album=album,
                    release_year=release_year,
                    album_art_url=album_art_url,
                    genres=genres,
                    tags=tags,
                    embedding=embedding,
                    enriched_at=datetime.now(timezone.utc),
                )
                db.add(track)
                await db.flush()
                print(f"  → Enriched and stored (spotify_id: {spotify_id})")
            else:
                print(f"  → Already in tracks table")

            # Check if already in demo user's collection
            ct_result = await db.execute(
                select(CollectionTrack).where(
                    CollectionTrack.user_id == demo_user_id,
                    CollectionTrack.track_id == track.id,
                )
            )
            if ct_result.scalar_one_or_none():
                print("  → Already in demo collection")
                skipped += 1
            else:
                db.add(CollectionTrack(
                    user_id=demo_user_id,
                    track_id=track.id,
                    source=CollectionSource.DEMO_SEED,
                ))
                added += 1

            # Commit every 50 tracks to avoid losing progress
            if i % 50 == 0:
                await db.commit()
                print(f"  [checkpoint] committed {i} tracks")

            time.sleep(SPOTIFY_SEARCH_DELAY)

        await db.commit()

    await engine.dispose()
    print(f"\nDone. Added {added} tracks to demo collection, skipped {skipped}.")
    if not settings.demo_user_id:
        print(f"Set DEMO_USER_ID={demo_user_id} in your environment.")


if __name__ == "__main__":
    asyncio.run(main())
