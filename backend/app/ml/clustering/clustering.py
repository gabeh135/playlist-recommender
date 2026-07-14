from dataclasses import dataclass

import numpy as np
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score
from sklearn.metrics.pairwise import pairwise_distances
from sklearn.preprocessing import normalize

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import CollectionTrack, Track

MIN_TRACKS = 10
MAX_AUTO_CLUSTERS = 25
SILHOUETTE_TOLERANCE = 0.02

@dataclass
class ClusterResult:
    track_ids: list[str]
    centroid: list[float]
    # TODO: store representative id for playlist naming

async def load_embeddings(user_id: str, db: AsyncSession) -> list[tuple[str, list[float]]]:
    result = await db.execute(
        select(Track.id, Track.embedding)
        .join(CollectionTrack, CollectionTrack.track_id == Track.id)
        .where(CollectionTrack.user_id == user_id)
        .where(Track.embedding.isnot(None))
    )
    return [(track_id, embedding) for track_id, embedding in result.all()]


def _find_optimal_k(matrix, distance_matrix, max_k: int) -> int:
    scores: dict[int, float] = {}

    for k in range(2, max_k + 1):
        kmeans = KMeans(n_clusters=k, random_state=42)
        kmeans.fit(matrix)
        scores[k] = silhouette_score(distance_matrix, kmeans.labels_, metric="precomputed")

    best_score = max(scores.values())
    # choose the largest k that's within tolerance to avoid bias towards smaller k
    candidates = [k for k, score in scores.items() if score >= best_score - SILHOUETTE_TOLERANCE]
    return max(candidates)


def _outlier_indices(matrix, labels, centroids, threshold_multiplier: float) -> set[int]:
    outliers = set()
    for c, centroid in enumerate(centroids):
        member_indices = np.where(labels == c)[0]
        distances = np.linalg.norm(matrix[member_indices] - centroid, axis=1)
        median_dist = np.median(distances)
        flagged = member_indices[distances > threshold_multiplier * median_dist]
        outliers.update(flagged.tolist())
    return outliers


# TODO: move this call into an async Celery task
def cluster_collection(
    track_ids: list[str],
    matrix,
    outlier_threshold: float = 1.5,
    n_clusters: int | None = None,
) -> tuple[list[ClusterResult], float | None, list[str]]:
    n = len(track_ids)
    if n < MIN_TRACKS:
        raise ValueError(f"Need at least {MIN_TRACKS} tracks to cluster (got {n})")

    matrix = normalize(matrix)
    distance_matrix = pairwise_distances(matrix)

    if n_clusters is not None:
        k = n_clusters
    else:
        max_k = min(max(2, n // 8), MAX_AUTO_CLUSTERS)
        k = _find_optimal_k(matrix, distance_matrix, max_k)

    kmeans = KMeans(n_clusters=k, random_state=42)
    kmeans.fit(matrix)

    labels = kmeans.labels_
    centroids = kmeans.cluster_centers_
    # silhouette_score needs 2 to n-1 distinct labels
    score = silhouette_score(distance_matrix, labels, metric="precomputed") if (2 <= k <= n - 1) else None
    outliers = _outlier_indices(matrix, labels, centroids, outlier_threshold)

    results = []
    for c in range(k):
        members = np.array([i for i, label in enumerate(labels) if label == c and i not in outliers])
        centroid = centroids[c]

        distances = np.linalg.norm(matrix[members] - centroid, axis=1)
        sorted_indices = np.argsort(distances)
        sorted_members = members[sorted_indices]

        ordered_ids = [track_ids[i] for i in sorted_members]
        results.append(ClusterResult(
            track_ids=ordered_ids,
            centroid=centroids[c].tolist(),
        ))

    outlier_track_ids = [track_ids[i] for i in outliers]
    return results, score, outlier_track_ids
