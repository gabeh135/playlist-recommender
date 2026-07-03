import asyncio

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_user
from app.ml.encoders.embed import embed_text
from app.ml.retrieval import search_collection
from app.models import GenerationMode, IntentSession, Playlist, PlaylistTrack, Track, User
from app.services.claude_client import expand_query

router = APIRouter(prefix="/playlists", tags=["playlists"])


class GenerateRequest(BaseModel):
    prompt: str
    limit: int = 20


class PlaylistTrackItem(BaseModel):
    position: int
    score: float
    spotify_id: str
    title: str
    artist: str
    album: str
    album_art_url: str | None


class GenerateResponse(BaseModel):
    playlist_id: str
    name: str
    tracks: list[PlaylistTrackItem]


@router.post("/generate", response_model=GenerateResponse, status_code=201)
async def generate_playlist(
    body: GenerateRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    expanded_prompt = await asyncio.to_thread(expand_query, body.prompt)
    query_embedding = embed_text(expanded_prompt)

    intent_session = IntentSession(
        user_id=user.id,
        raw_prompt=body.prompt,
        intent_embedding=query_embedding,
    )
    db.add(intent_session)
    await db.flush()  # need intent_session.id before the Playlist row references it

    results = await search_collection(user.id, query_embedding, body.limit, db)
    if not results:
        raise HTTPException(status_code=422, detail="Collection is empty or no tracks have embeddings")

    playlist = Playlist(
        user_id=user.id,
        name=body.prompt[:120],
        generation_mode=GenerationMode.TARGETED,
        intent_session_id=intent_session.id,
    )
    db.add(playlist)
    await db.flush()

    for i, (track, _score) in enumerate(results):
        db.add(PlaylistTrack(
            playlist_id=playlist.id,
            track_id=track.id,
            position=i,
        ))

    await db.commit()

    return GenerateResponse(
        playlist_id=playlist.id,
        name=playlist.name,
        tracks=[
            PlaylistTrackItem(
                position=i,
                score=round(score, 4),
                spotify_id=track.spotify_id,
                title=track.title,
                artist=track.artist,
                album=track.album,
                album_art_url=track.album_art_url,
            )
            for i, (track, score) in enumerate(results)
        ],
    )


@router.get("/{playlist_id}", response_model=GenerateResponse)
async def get_playlist(
    playlist_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Playlist).where(Playlist.id == playlist_id, Playlist.user_id == user.id)
    )
    playlist = result.scalar_one_or_none()
    if not playlist:
        raise HTTPException(status_code=404, detail="Playlist not found")

    rows = await db.execute(
        select(Track, PlaylistTrack)
        .join(PlaylistTrack, PlaylistTrack.track_id == Track.id)
        .where(PlaylistTrack.playlist_id == playlist_id)
        .order_by(PlaylistTrack.position)
    )

    return GenerateResponse(
        playlist_id=playlist.id,
        name=playlist.name,
        tracks=[
            PlaylistTrackItem(
                position=pt.position,
                score=0.0,  # scores aren't persisted; only position is stored in PlaylistTrack
                spotify_id=track.spotify_id,
                title=track.title,
                artist=track.artist,
                album=track.album,
                album_art_url=track.album_art_url,
            )
            for track, pt in rows.all()
        ],
    )
