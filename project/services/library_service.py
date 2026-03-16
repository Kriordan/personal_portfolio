"""Business logic shared by library web and API routes."""

from __future__ import annotations

from typing import Any

from project.library.jobs import sync_playlists_and_videos
from project.models import Playlist, Video


class LibraryServiceError(Exception):
    """Base library service exception."""


class NotFoundError(LibraryServiceError):
    """Raised when requested library content does not exist."""


def serialize_playlist(playlist: Playlist) -> dict[str, Any]:
    """Return a JSON-safe playlist payload."""
    return {
        "id": playlist.id,
        "title": playlist.title,
        "description": playlist.description,
        "published_at": playlist.published_at.isoformat() if playlist.published_at else None,
        "updated_at": playlist.updated_at.isoformat() if playlist.updated_at else None,
        "thumbnail_url": playlist.thumbnail_url,
    }


def serialize_video(video: Video) -> dict[str, Any]:
    """Return a JSON-safe video payload."""
    return {
        "id": video.id,
        "playlist_id": video.playlist_id,
        "video_url_id": video.video_url_id,
        "title": video.title,
        "description": video.description,
        "published_at": video.published_at.isoformat() if video.published_at else None,
        "thumbnail_url": video.thumbnail_url,
        "embed_url": video.embed_url,
        "watched": video.watched,
        "created_at": video.created_at.isoformat() if video.created_at else None,
        "updated_at": video.updated_at.isoformat() if video.updated_at else None,
    }


def list_playlists() -> list[Playlist]:
    """Return playlists sorted by most recently published first."""
    return Playlist.query.order_by(Playlist.published_at.desc()).all()


def get_playlist_with_videos(*, playlist_id: str) -> tuple[Playlist, list[Video]]:
    """Return a playlist and its videos, raising if playlist is not found."""
    playlist = Playlist.query.get(playlist_id)
    if playlist is None:
        raise NotFoundError("playlist not found")
    videos = Video.query.filter_by(playlist_id=playlist_id).order_by(Video.published_at.desc()).all()
    return playlist, videos


def get_video(*, video_id: str) -> Video:
    """Return a video by ID, raising if not found."""
    video = Video.query.get(video_id)
    if video is None:
        raise NotFoundError("video not found")
    return video


def sync_library() -> None:
    """Synchronize playlists and videos from YouTube."""
    sync_playlists_and_videos()
