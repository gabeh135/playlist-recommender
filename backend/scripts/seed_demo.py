"""script to seed the demo user's collection with ~1000 tracks sampled across Last.fm genre tags"""

import asyncio
import os
import sys
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
BATCH_SIZE = 50
GENRE_TAGS = [
    "pop", "rock", "hip-hop", "r&b", "electronic", "country",
    "indie", "metal", "jazz", "k-pop", "latin", "folk",
    "punk", "reggae", "classical",
]


def get_lastfm_tracks_by_tag(api_key: str, tag: str, limit: int) -> list[dict]:
    client = httpx.Client()
    resp = client.get(
        "http://ws.audioscrobbler.com/2.0/",
        params={
            "method": "tag.gettoptracks",
            "tag": tag,
            "limit": limit,
            "api_key": api_key,
            "format": "json",
        },
    ).json()

    raw = resp.get("tracks", {}).get("track", [])
    return [{"title": t["name"], "artist": t["artist"]["name"]} for t in raw]


def get_lastfm_top_tracks(api_key: str, target: int) -> list[dict]:
    """Samples across genre tags instead of one global chart, so the seed collection spans genres instead of skewing toward whatever's currently most-scrobbled overall."""
    per_tag = target // len(GENRE_TAGS)
    seen = set()
    tracks = []

    for tag in GENRE_TAGS:
        tag_tracks = get_lastfm_tracks_by_tag(api_key, tag, per_tag)
        print(f"  {tag}: {len(tag_tracks)} tracks")

        for t in tag_tracks:
            key = (t["title"].lower(), t["artist"].lower())
            if key not in seen:
                seen.add(key)
                tracks.append(t)

    return tracks[:target]


async def process_batch(batch, start_index, total, demo_user_id, spotify, lastfm, db):
    resolved: list[dict | None] = []
    for offset, candidate in enumerate(batch):
        i = start_index + offset + 1
        title = candidate["title"]
        artist = candidate["artist"]
        print(f"[{i}/{total}] resolving {title} — {artist}")

        try:
            results = spotify.search_tracks(f"{artist} {title}", limit=1)
        except Exception as e:
            status = getattr(e, "http_status", None)
            if status == 429:
                wait = (getattr(e, "headers", None) or {}).get("Retry-After", "unknown")
                print(f"  [temporary] rate limited, retrying in {wait}s — skipping this candidate for now")
            else:
                print(f"  [temporary] Spotify search failed: {e} — skipping")
            resolved.append(None)
            continue

        if not results:
            print("  Not found on Spotify — skipping")
            resolved.append(None)
            continue

        raw = results[0]
        existing = await db.execute(select(Track).where(Track.spotify_id == raw["id"]))
        resolved.append({"raw": raw, "track": existing.scalar_one_or_none()})

    new_entries = [r for r in resolved if r is not None and r["track"] is None]
    artist_ids = list({r["raw"]["artists"][0]["id"] for r in new_entries})
    genre_map = spotify.get_artist_genres(artist_ids) if artist_ids else {}
    print(f"  Fetched genres for {len(artist_ids)} unique artists")

    added = 0
    skipped = 0

    for offset, entry in enumerate(resolved):
        i = start_index + offset + 1
        if entry is None:
            skipped += 1
            continue

        raw = entry["raw"]
        track = entry["track"]

        if track is None:
            artist_id = raw["artists"][0]["id"]
            artist_name = raw["artists"][0]["name"]
            track_title = raw["name"]
            print(f"[{i}/{total}] {track_title} — {artist_name}")
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

            genres = genre_map.get(artist_id, [])
            tags = lastfm.get_track_tags(artist_name, track_title)

            embedding_input = f"{track_title} by {artist_name}. Genres: {', '.join(genres)}. Tags: {', '.join(tags)}"
            embedding = embed_text(embedding_input)
            genre_tag_input = f"Genres: {', '.join(genres)}. Tags: {', '.join(tags)}"
            genre_tag_embedding = embed_text(genre_tag_input)

            track = Track(
                spotify_id=raw["id"],
                title=track_title,
                artist=artist_name,
                album=album,
                release_year=release_year,
                album_art_url=album_art_url,
                genres=genres,
                tags=tags,
                embedding=embedding,
                genre_tag_embedding=genre_tag_embedding,
                enriched_at=datetime.now(timezone.utc),
            )
            db.add(track)
            await db.flush()
            print(f"  → Enriched and stored (spotify_id: {track.spotify_id})")
        else:
            print(f"[{i}/{total}] {track.title} — {track.artist}")
            print("  → Already in tracks table")

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

    await db.commit()
    return added, skipped


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

        for batch_start in range(0, len(candidates), BATCH_SIZE):
            batch = candidates[batch_start:batch_start + BATCH_SIZE]
            batch_added, batch_skipped = await process_batch(
                batch, batch_start, len(candidates), demo_user_id, spotify, lastfm, db
            )
            added += batch_added
            skipped += batch_skipped
            print(f"  [checkpoint] committed through {batch_start + len(batch)}/{len(candidates)}")

    await engine.dispose()
    print(f"\nDone. Added {added} tracks to demo collection, skipped {skipped}.")
    if not settings.demo_user_id:
        print(f"Set DEMO_USER_ID={demo_user_id} in your environment.")


if __name__ == "__main__":
    asyncio.run(main())
