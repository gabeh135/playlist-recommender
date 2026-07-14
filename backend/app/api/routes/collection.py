import asyncio
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func, insert, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.deps import get_current_user
from app.ml.encoders.embed import embed_text
from app.models import CollectionSource, CollectionTrack, Track, User
from app.services.lastfm_client import LastFmClient
from app.services.spotify_client import SpotifyClient

router = APIRouter(prefix="/collection", tags=["collection"])

spotify = SpotifyClient()
lastfm = LastFmClient()


def _parse_playlist_id(url_or_id: str) -> str:
    if url_or_id.startswith("http"):
        return url_or_id.split("?")[0].split("/")[-1]
    return url_or_id


class AddTrackRequest(BaseModel):
    spotify_id: str


class ImportPlaylistRequest(BaseModel):
    playlist_url: str


class CollectionTrackResponse(BaseModel):
    track_id: str
    spotify_id: str
    title: str
    artist: str
    album: str
    release_year: int | None
    album_art_url: str | None
    added_at: str
    source: str


class CollectionPageResponse(BaseModel):
    items: list[CollectionTrackResponse]
    total: int


@router.post("/tracks", status_code=201)
async def add_track(
    body: AddTrackRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Track).where(Track.spotify_id == body.spotify_id))
    track = result.scalar_one_or_none()

    if track is None:
        raw = await asyncio.to_thread(spotify.get_track, body.spotify_id)
        if raw is None:
            raise HTTPException(status_code=404, detail="Track not found on Spotify")

        artist_id = raw["artists"][0]["id"]
        artist_name = raw["artists"][0]["name"]
        title = raw["name"]
        album = raw.get("album", {}).get("name", "")

        release_year = None
        rd = raw.get("album", {}).get("release_date", "")
        if rd:
            try:
                # Spotify returns dates as YYYY, YYYY-MM, or YYYY-MM-DD
                release_year = int(rd[:4])
            except ValueError:
                pass

        images = raw.get("album", {}).get("images", [])
        album_art_url = images[0]["url"] if images else None

        genre_map = await asyncio.to_thread(spotify.get_artist_genres, [artist_id])
        genres = genre_map.get(artist_id, [])
        tags = await asyncio.to_thread(lastfm.get_track_tags, artist_name, title)

        embedding_input = f"{title} by {artist_name}. Genres: {', '.join(genres)}. Tags: {', '.join(tags)}"
        embedding = await asyncio.to_thread(embed_text, embedding_input)
        genre_tag_input = f"Genres: {', '.join(genres)}. Tags: {', '.join(tags)}"
        genre_tag_embedding = await asyncio.to_thread(embed_text, genre_tag_input)

        track = Track(
            spotify_id=body.spotify_id,
            title=title,
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
        await db.flush()  # need track.id before the CollectionTrack insert

    existing = await db.execute(
        select(CollectionTrack).where(
            CollectionTrack.user_id == user.id,
            CollectionTrack.track_id == track.id,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Track already in collection")

    ct = CollectionTrack(
        user_id=user.id,
        track_id=track.id,
        source=CollectionSource.SEARCH,
    )
    db.add(ct)
    await db.commit()

    return {"track_id": track.id, "spotify_id": track.spotify_id, "title": track.title}


@router.post("/import/playlist", status_code=201)
async def import_playlist(
    body: ImportPlaylistRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    playlist_id = _parse_playlist_id(body.playlist_url)

    try:
        raw_tracks = await asyncio.to_thread(spotify.get_playlist_tracks, playlist_id)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Spotify error: {e}")

    if not raw_tracks:
        raise HTTPException(status_code=404, detail="Playlist not found or empty")

    raw_tracks = [t for t in raw_tracks if t.get("id")]  # Spotify includes null entries for unavailable tracks

    spotify_ids = [t["id"] for t in raw_tracks]
    result = await db.execute(select(Track).where(Track.spotify_id.in_(spotify_ids)))
    known_tracks: dict[str, Track] = {t.spotify_id: t for t in result.scalars().all()}

    new_raw = [t for t in raw_tracks if t["id"] not in known_tracks]

    artist_ids = list({t["artists"][0]["id"] for t in new_raw})  # set dedup avoids redundant genre calls for shared artists
    genre_map = await asyncio.to_thread(spotify.get_artist_genres, artist_ids) if artist_ids else {}

    track_pairs = [(t["artists"][0]["name"], t["name"]) for t in new_raw]
    tags_map = await asyncio.to_thread(lastfm.get_track_tags_batch, track_pairs) if track_pairs else {}

    new_tracks: dict[str, Track] = {}
    for raw in new_raw:
        artist_id = raw["artists"][0]["id"]
        artist_name = raw["artists"][0]["name"]
        title = raw["name"]
        album = raw.get("album", {}).get("name", "")

        release_year = None
        rd = raw.get("album", {}).get("release_date", "")
        if rd:
            try:
                # Spotify returns dates as YYYY, YYYY-MM, or YYYY-MM-DD
                release_year = int(rd[:4])
            except ValueError:
                pass

        images = raw.get("album", {}).get("images", [])
        album_art_url = images[0]["url"] if images else None

        genres = genre_map.get(artist_id, [])
        tags = tags_map.get((artist_name, title), [])

        embedding_input = f"{title} by {artist_name}. Genres: {', '.join(genres)}. Tags: {', '.join(tags)}"
        embedding = await asyncio.to_thread(embed_text, embedding_input)
        genre_tag_input = f"Genres: {', '.join(genres)}. Tags: {', '.join(tags)}"
        genre_tag_embedding = await asyncio.to_thread(embed_text, genre_tag_input)

        track = Track(
            spotify_id=raw["id"],
            title=title,
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
        new_tracks[raw["id"]] = track

    await db.flush()  # assigns PKs to new Track rows before CollectionTrack inserts reference them

    all_tracks = {**known_tracks, **new_tracks}

    all_track_ids = [t.id for t in all_tracks.values()]
    result = await db.execute(
        select(CollectionTrack.track_id).where(
            CollectionTrack.user_id == user.id,
            CollectionTrack.track_id.in_(all_track_ids),
        )
    )
    already_collected = {row[0] for row in result.all()}

    added = 0
    for raw in raw_tracks:
        track = all_tracks.get(raw["id"])
        if track is None or track.id in already_collected:
            continue
        db.add(CollectionTrack(
            user_id=user.id,
            track_id=track.id,
            source=CollectionSource.PLAYLIST_IMPORT,
            source_spotify_playlist_id=playlist_id,
        ))
        added += 1

    await db.commit()
    return {"imported": added, "skipped": len(raw_tracks) - added}


@router.get("/tracks", response_model=CollectionPageResponse)
async def get_collection(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
):
    total_result = await db.execute(
        select(func.count())
        .select_from(CollectionTrack)
        .where(CollectionTrack.user_id == user.id)
    )
    total = total_result.scalar_one()

    result = await db.execute(
        select(Track, CollectionTrack)
        .join(CollectionTrack, CollectionTrack.track_id == Track.id)
        .where(CollectionTrack.user_id == user.id)
        .order_by(CollectionTrack.added_at.desc())
        .limit(limit)
        .offset(offset)
    )
    rows = result.all()

    return CollectionPageResponse(
        total=total,
        items=[
            CollectionTrackResponse(
                track_id=track.id,
                spotify_id=track.spotify_id,
                title=track.title,
                artist=track.artist,
                album=track.album,
                release_year=track.release_year,
                album_art_url=track.album_art_url,
                added_at=str(ct.added_at),
                source=ct.source,
            )
            for track, ct in rows
        ],
    )


@router.post("/demo", status_code=201)
async def load_demo_collection(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not settings.demo_user_id:
        raise HTTPException(status_code=503, detail="Demo collection not available")

    demo_result = await db.execute(
        select(CollectionTrack.track_id).where(
            CollectionTrack.user_id == settings.demo_user_id
        )
    )
    demo_track_ids = [row[0] for row in demo_result.all()]

    if not demo_track_ids:
        raise HTTPException(status_code=503, detail="Demo collection is empty")

    # skip existng results
    existing_result = await db.execute(
        select(CollectionTrack.track_id).where(
            CollectionTrack.user_id == user.id,
            CollectionTrack.track_id.in_(demo_track_ids),
        )
    )
    already_owned = {row[0] for row in existing_result.all()}

    new_track_ids = [tid for tid in demo_track_ids if tid not in already_owned]

    if new_track_ids:
        await db.execute(
            insert(CollectionTrack).values([
                {
                    "user_id": user.id,
                    "track_id": tid,
                    "source": CollectionSource.DEMO_SEED,
                }
                for tid in new_track_ids
            ])
        )
        await db.commit()

    return {"added": len(new_track_ids), "skipped": len(already_owned)}
