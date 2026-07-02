import requests
import spotipy
import urllib3
from spotipy.oauth2 import SpotifyClientCredentials

from app.core.config import settings


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
