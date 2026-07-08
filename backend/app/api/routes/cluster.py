import asyncio
from datetime import datetime, timezone

import numpy as np
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_user
from app.ml.clustering.clustering import ClusterResult, cluster_collection, load_embeddings, MIN_TRACKS
from app.models import ClusteringRun, GenerationMode, Playlist, PlaylistTrack, Track, User
from app.services.claude_client import name_playlist

NAMING_SAMPLE_SIZE = 5

router = APIRouter(prefix="/cluster", tags=["cluster"])


async def _name_clusters(
    results: list[ClusterResult], track_map: dict[str, Track]
) -> list[str | None]:
    """Name each cluster from a sample of its centroid-closest tracks"""
    samples = []
    for result in results:
        sample_titles = []
        for track_id in result.track_ids[:NAMING_SAMPLE_SIZE]:
            track = track_map.get(track_id)
            if track:
                sample_titles.append(f"{track.title} by {track.artist}")
        samples.append(sample_titles)

    return await asyncio.gather(*[asyncio.to_thread(name_playlist, sample) for sample in samples])


class ClusterRequest(BaseModel):
    n_clusters: int | None = None
    outlier_threshold: float = 1.5


class ClusterTrackItem(BaseModel):
    position: int
    track_id: str
    title: str
    artist: str
    album_art_url: str | None


class ClusterPlaylistItem(BaseModel):
    id: str
    name: str
    tracks: list[ClusterTrackItem]


class ClusterResponse(BaseModel):
    clustering_run_id: str
    n_clusters: int
    tracks_placed: int
    outliers_excluded: int
    playlists: list[ClusterPlaylistItem]


@router.post("", response_model=ClusterResponse, status_code=201)
async def create_cluster(
    body: ClusterRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    embeddings = await load_embeddings(user.id, db)
    if len(embeddings) < MIN_TRACKS:
        raise HTTPException(
            status_code=400,
            detail=f"At least {MIN_TRACKS} tracks required to cluster (collection has {len(embeddings)})",
        )

    track_ids, vectors = zip(*embeddings)
    track_ids = list(track_ids)
    matrix = np.array(vectors)

    # run async as k-means can take time
    results = await asyncio.to_thread(
        cluster_collection, track_ids, matrix, body.outlier_threshold, body.n_clusters
    )

    run = ClusteringRun(
        user_id=user.id,
        n_clusters=len(results),
        algorithm="kmeans",
        outlier_threshold=body.outlier_threshold,
        run_at=datetime.now(timezone.utc),
    )
    db.add(run)
    await db.flush()

    result_rows = await db.execute(select(Track).where(Track.id.in_(track_ids)))
    track_map: dict[str, Track] = {t.id: t for t in result_rows.scalars().all()}

    names = await _name_clusters(results, track_map)

    playlists_out: list[ClusterPlaylistItem] = []
    tracks_placed = 0

    for i, (result, llm_name) in enumerate(zip(results, names)):
        name = llm_name or f"Playlist {i + 1}"
        playlist = Playlist(
            user_id=user.id,
            clustering_run_id=run.id,
            name=name,
            generation_mode=GenerationMode.CLUSTERED,
        )
        db.add(playlist)
        await db.flush()

        track_rows = []
        track_items = []
        for position, track_id in enumerate(result.track_ids):
            track_rows.append(PlaylistTrack(playlist_id=playlist.id, track_id=track_id, position=position))
            t = track_map.get(track_id)
            if t:
                track_items.append(ClusterTrackItem(
                    position=position,
                    track_id=track_id,
                    title=t.title,
                    artist=t.artist,
                    album_art_url=t.album_art_url,
                ))
        db.add_all(track_rows)
        tracks_placed += len(track_rows)

        playlists_out.append(ClusterPlaylistItem(id=playlist.id, name=name, tracks=track_items))

    await db.commit()

    return ClusterResponse(
        clustering_run_id=run.id,
        n_clusters=run.n_clusters,
        tracks_placed=tracks_placed,
        outliers_excluded=len(track_ids) - tracks_placed,
        playlists=playlists_out,
    )
