import threading
import time
from collections import deque

import requests
import spotipy
import urllib3
from spotipy.oauth2 import SpotifyClientCredentials

from app.core.config import settings


class _RateLimiter:
    """Spotify doesn't publish the actual dev-mode quota, so max_calls/period
    is a conservative guess not a known number.
    """

    def __init__(self, max_calls: int, period: float):
        self._max_calls = max_calls
        self._period = period
        self._calls: deque[float] = deque()
        self._lock = threading.Lock()

    def acquire(self):
        with self._lock:
            now = time.monotonic()
            while self._calls and now - self._calls[0] > self._period:
                self._calls.popleft()

            if len(self._calls) >= self._max_calls:
                wait = self._period - (now - self._calls[0])
                if wait > 0:
                    time.sleep(wait)
                now = time.monotonic()
                while self._calls and now - self._calls[0] > self._period:
                    self._calls.popleft()

            self._calls.append(now)


class SpotifyClient:
    def __init__(self):
        self._sp = spotipy.Spotify(
            auth_manager=SpotifyClientCredentials(
                client_id=settings.spotify_client_id,
                client_secret=settings.spotify_client_secret,
                requests_timeout=10,
            ),
            requests_timeout=10,
        )

        retry = urllib3.Retry(
            total=3,
            status_forcelist=(429, 500, 502, 503, 504),
            backoff_factor=0.5,
            respect_retry_after_header=False,
        )
        adapter = requests.adapters.HTTPAdapter(max_retries=retry)
        self._sp._session.mount("https://", adapter)
        self._sp._session.mount("http://", adapter)

        self._limiter = _RateLimiter(max_calls=30, period=30.0)
        original_send = self._sp._session.send

        def _throttled_send(request, **kwargs):
            self._limiter.acquire()
            return original_send(request, **kwargs)

        self._sp._session.send = _throttled_send

    def search_tracks(self, query: str, limit: int) -> list[dict]:
        results = []
        offset = 0

        while len(results) < limit:
            batch_size = min(10, limit - len(results))  # Spotify caps search results at 10 per request (Feb 2026)
            response = self._sp.search(q=query, type="track", limit=batch_size, offset=offset)

            items = response["tracks"]["items"]
            if not items:
                break

            results.extend(items)
            offset += len(items)

        return results

    def get_artist_genres(self, artist_ids: list[str]) -> dict[str, list[str]]:
        genres = {}
        for artist_id in artist_ids:
            try:
                artist = self._sp.artist(artist_id)
                genres[artist["id"]] = artist["genres"]
            except Exception:
                genres[artist_id] = []
        return genres

    def get_track(self, spotify_id: str) -> dict | None:
        try:
            return self._sp.track(spotify_id)
        except Exception:
            try:
                return self._sp.track(spotify_id)
            except Exception:
                return None

    def get_playlist_tracks(self, playlist_id: str) -> list[dict]:
        tracks = []

        response = self._sp.playlist_items(playlist_id, limit=100)
        while response:
            # Spotify returns null entries for locally unavailable or removed tracks
            items = [item["item"] for item in response["items"] if item.get("item") is not None]
            tracks.extend(items)
            response = self._sp.next(response) if response["next"] else None

        return tracks
