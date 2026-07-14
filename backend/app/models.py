import enum
from uuid import uuid4

from pgvector.sqlalchemy import Vector
from sqlalchemy import ARRAY, Enum, Float, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql.sqltypes import DateTime

from app.core.database import Base


class GenerationMode(str, enum.Enum):
    TARGETED = "TARGETED"
    CLUSTERED = "CLUSTERED"


class CollectionSource(str, enum.Enum):
    SEARCH = "SEARCH"
    PLAYLIST_IMPORT = "PLAYLIST_IMPORT"
    LIKED_SONGS = "LIKED_SONGS"
    DEMO_SEED = "DEMO_SEED"


class FeedbackType(str, enum.Enum):
    LIKE = "LIKE"
    DISLIKE = "DISLIKE"
    SKIP = "SKIP"
    SAVE_PLAYLIST = "SAVE_PLAYLIST"
    DISMISS = "DISMISS"


class Track(Base):
    __tablename__ = "tracks"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    spotify_id: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    title: Mapped[str] = mapped_column(String, nullable=False)
    artist: Mapped[str] = mapped_column(String, nullable=False)
    album: Mapped[str] = mapped_column(String, nullable=False)
    release_year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    album_art_url: Mapped[str] = mapped_column(String, nullable=True)
    genres: Mapped[list[str] | None] = mapped_column(ARRAY(String), nullable=True)
    tags: Mapped[list[str] | None] = mapped_column(ARRAY(String), nullable=True)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(384), nullable=True)
    enriched_at: Mapped[str | None] = mapped_column(DateTime(timezone=True), nullable=True)


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    spotify_user_id: Mapped[str | None] = mapped_column(String, nullable=True)
    spotify_access_token: Mapped[str | None] = mapped_column(String, nullable=True)
    spotify_refresh_token: Mapped[str | None] = mapped_column(String, nullable=True)
    spotify_token_expires_at: Mapped[str | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # needed to detect Spotify-policy 6-month expiry
    spotify_authorized_at: Mapped[str | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[str] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class CollectionTrack(Base):
    __tablename__ = "collection_tracks"
    __table_args__ = (UniqueConstraint("user_id", "track_id", name="uq_collection_user_track"),)

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    user_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("users.id"), nullable=False)
    track_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("tracks.id"), nullable=False)
    added_at: Mapped[str] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    source: Mapped[str] = mapped_column(Enum(CollectionSource, name="collection_source_enum"), nullable=False)
    source_spotify_playlist_id: Mapped[str | None] = mapped_column(String, nullable=True)


class IntentSession(Base):
    __tablename__ = "intent_sessions"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    user_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("users.id"), nullable=False)
    raw_prompt: Mapped[str] = mapped_column(String, nullable=False)
    intent_embedding: Mapped[list[float] | None] = mapped_column(Vector(384), nullable=True)
    created_at: Mapped[str] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class ClusteringRun(Base):
    __tablename__ = "clustering_runs"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    user_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("users.id"), nullable=False)
    n_clusters: Mapped[int] = mapped_column(Integer, nullable=False)
    algorithm: Mapped[str] = mapped_column(String, nullable=False)
    outlier_threshold: Mapped[float] = mapped_column(Float, nullable=False)
    silhouette_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    run_at: Mapped[str] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class Playlist(Base):
    __tablename__ = "playlists"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    user_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("users.id"), nullable=False)
    intent_session_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False), ForeignKey("intent_sessions.id"), nullable=True
    )
    clustering_run_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False), ForeignKey("clustering_runs.id"), nullable=True
    )
    name: Mapped[str] = mapped_column(String, nullable=False)
    generation_mode: Mapped[str] = mapped_column(
        Enum(GenerationMode, name="generation_mode_enum"), nullable=False
    )
    created_at: Mapped[str] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class PlaylistTrack(Base):
    __tablename__ = "playlist_tracks"
    __table_args__ = (UniqueConstraint("playlist_id", "track_id", name="uq_playlist_track"),)

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    playlist_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("playlists.id"), nullable=False)
    track_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("tracks.id"), nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)


class FeedbackEvent(Base):
    __tablename__ = "feedback_events"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    user_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("users.id"), nullable=False)
    track_id: Mapped[str | None] = mapped_column(UUID(as_uuid=False), ForeignKey("tracks.id"), nullable=True)
    playlist_id: Mapped[str | None] = mapped_column(UUID(as_uuid=False), ForeignKey("playlists.id"), nullable=True)
    type: Mapped[str] = mapped_column(Enum(FeedbackType, name="feedback_type_enum"), nullable=False)
    position: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[str] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
