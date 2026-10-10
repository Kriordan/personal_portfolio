"""Business logic shared by library web and API routes."""

from __future__ import annotations

from typing import Any
from datetime import datetime, timezone
from uuid import uuid4

from flask import current_app
from google.auth.exceptions import RefreshError, TransportError
from googleapiclient.errors import HttpError
from httplib2 import HttpLib2Error

from project.database import db
from project.library.jobs import YouTubeConfigurationError, sync_playlists_and_videos
from project.models import LibrarySyncRun, Playlist, Video
from project.library.sync_tracking import import_lock, recover_interrupted_runs, serialize_run


class LibraryServiceError(Exception):
    """Base library service exception."""


class NotFoundError(LibraryServiceError):
    """Raised when requested library content does not exist."""


class SyncError(LibraryServiceError):
    """Safe response details for web and API callers; never includes provider text."""

    def __init__(self, message: str, status: int):
        super().__init__(message)
        self.status = status


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
        "position": video.position,
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


def sync_library(request_id=None):
    """A durable receipt survives a lost HTTP response; imports never auto-replay."""
    request_id = request_id or str(uuid4())
    with import_lock() as acquired:
        if not acquired:
            raise SyncError("A shared Library sync is already running. Check its status before trying again.", 409)
        recover_interrupted_runs()
        existing = db.session.get(LibrarySyncRun, request_id)
        if existing:
            return serialize_run(existing)
        run = LibrarySyncRun(id=request_id, status="running", started_at=datetime.now(timezone.utc))
        db.session.add(run)
        db.session.commit()
        current_app.logger.info("Library sync started: %s", request_id)
        try:
            summary = sync_playlists_and_videos(commit=False)
            # Explicitly fence final commit if the lock connection was lost and a
            # status check/new importer has already marked this run interrupted.
            changed = LibrarySyncRun.query.filter_by(id=request_id, status="running").update({
                "status": "succeeded", "finished_at": datetime.now(timezone.utc),
                "summary": summary if isinstance(summary, dict) else None,
            }, synchronize_session=False)
            if changed != 1:
                raise SyncError("The import was interrupted. Check its status before trying again.", 409)
            db.session.commit()
            db.session.expire_all()
            current_app.logger.info("Library sync completed: %s", request_id)
            return serialize_run(db.session.get(LibrarySyncRun, request_id))
        except Exception as error:
            db.session.rollback()
            current_app.logger.warning("Library sync failed: %s (%s)", request_id, type(error).__name__)
            if isinstance(error, SyncError):
                safe = error
            elif isinstance(error, (YouTubeConfigurationError, RefreshError)) or (
                isinstance(error, HttpError) and error.resp.status == 401
            ):
                safe = SyncError("YouTube sync is unavailable. Ask the library maintainer to check its connection.", 503)
            elif isinstance(error, (HttpError, TransportError, HttpLib2Error, OSError)):
                safe = SyncError("YouTube could not complete the import. Try again later.", 502)
            else:
                safe = SyncError("Library sync failed. Try again later.", 500)
            LibrarySyncRun.query.filter_by(id=request_id, status="running").update({
                "status": "failed", "finished_at": datetime.now(timezone.utc), "error": str(safe),
            }, synchronize_session=False)
            db.session.commit()
            raise safe from error
