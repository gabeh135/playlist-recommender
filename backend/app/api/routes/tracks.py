import asyncio

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from app.services.spotify_client import spotify_client as spotify

router = APIRouter(prefix="/tracks", tags=["tracks"])


class TrackCandidate(BaseModel):
    spotify_id: str
    title: str
    artist: str
    album: str
    release_year: int | None
    album_art_url: str | None


@router.get("/search", response_model=list[TrackCandidate])
async def search_tracks(q: str = Query(..., min_length=1), limit: int = Query(10, ge=1, le=10)):
    try:
        raw = await asyncio.to_thread(spotify.search_tracks, q, limit)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Spotify error: {e}")

    results = []
    for t in raw:
        release_year = None
        rd = t.get("album", {}).get("release_date", "")
        if rd:
            try:
                # Spotify returns dates as YYYY, YYYY-MM, or YYYY-MM-DD
                release_year = int(rd[:4])
            except ValueError:
                pass

        images = t.get("album", {}).get("images", [])
        album_art_url = images[0]["url"] if images else None

        results.append(TrackCandidate(
            spotify_id=t["id"],
            title=t["name"],
            artist=t["artists"][0]["name"],
            album=t.get("album", {}).get("name", ""),
            release_year=release_year,
            album_art_url=album_art_url,
        ))

    return results
