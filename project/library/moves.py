"""Durable, conservative YouTube moves. Recovery performs reads, never inserts.

YouTube offers no transaction/idempotency key across insert and delete. An
ambiguous insert therefore stays unresolved unless a read finds the destination.
Deletion is retried only by an explicitly confirmed removal request.
"""
from datetime import datetime, timezone

from flask import current_app
from googleapiclient.errors import HttpError

from project.database import db
from project.library.credentials import WRITE_SCOPE
from project.library.jobs import get_youtube_service
from project.library.sync_tracking import assert_import_lock, import_lock, recover_interrupted_runs
from project.library.workflow import WorkflowError, active_workflow, channel_id, connected_owner, iso, owned_playlists
from project.models import LibraryMove, LibraryWatchedMembership, Playlist, Video, YouTubeConnection

UNRESOLVED = ("running", "partial", "unknown")


def serialize_move(move):
    return {name: getattr(move, name) for name in (
        "id", "source_entry_id", "source_playlist_id", "destination_playlist_id", "video_url_id",
        "video_title", "source_title", "destination_title", "status", "stage", "error") } | {
        "started_at": iso(move.started_at), "updated_at": iso(move.updated_at),
        "can_retry_removal": move.status == "partial",
    }


def require_owner(user):
    if not connected_owner(user):
        raise WorkflowError("Only the connected administrator can move videos or view move activity.", 403)


def require_access(service, move):
    connection = db.session.get(YouTubeConnection, 1)
    if (not connection or connection.connected_by_id != move.owner_id
            or connection.channel_id != move.channel_id
            or WRITE_SCOPE not in (connection.granted_scopes or [])):
        raise WorkflowError("Reconnect the original YouTube channel with playlist-change access before continuing.")
    if channel_id(service) != move.channel_id:
        raise WorkflowError("The YouTube channel changed. Reconnect the original channel before continuing.")
    owned_playlists(service, move.channel_id, [move.source_playlist_id, move.destination_playlist_id])


def commit_stage(move, stage, status="running", error=None):
    assert_import_lock()
    move.stage, move.status, move.error = stage, status, error
    move.updated_at = datetime.now(timezone.utc)
    db.session.commit()


def source_entry(service, move):
    items = service.playlistItems().list(part="snippet,contentDetails", id=move.source_entry_id, maxResults=1).execute().get("items", [])
    if not items:
        return None
    item = items[0]
    if (item["id"] != move.source_entry_id or item["snippet"].get("playlistId") != move.source_playlist_id
            or item["contentDetails"].get("videoId") != move.video_url_id):
        raise WorkflowError("The source entry changed. Refresh the playlist before continuing.")
    return item


def destination_entry(service, move):
    resource = service.playlistItems()
    request = resource.list(part="snippet,contentDetails", playlistId=move.destination_playlist_id, videoId=move.video_url_id, maxResults=50)
    while request is not None:
        response = request.execute()
        for item in response.get("items", []):
            if item["snippet"].get("playlistId") == move.destination_playlist_id and item["contentDetails"].get("videoId") == move.video_url_id:
                return item
        request = resource.list_next(request, response)
    return None


def save_destination(move, item):
    """Upsert the confirmed entry without changing any other playlist's rows."""
    snippet = item["snippet"]
    now = datetime.now(timezone.utc)
    video = db.session.get(Video, item["id"])
    if video is None:
        video = Video(id=item["id"], playlist_id=move.destination_playlist_id)
        db.session.add(video)
    if video.playlist_id != move.destination_playlist_id:
        raise WorkflowError("The returned playlist entry did not match the destination.")
    video.video_url_id, video.title = move.video_url_id, snippet.get("title", move.video_title)
    video.description = snippet.get("description")
    video.published_at = datetime.fromisoformat(snippet["publishedAt"].replace("Z", "+00:00"))
    video.thumbnail_url = snippet.get("thumbnails", {}).get("default", {}).get("url")
    video.embed_url = f"https://www.youtube.com/embed/{move.video_url_id}"
    video.position = snippet.get("position")
    video.updated_at = now
    move.destination_entry_id = item["id"]
    destination = db.session.get(Playlist, move.destination_playlist_id)
    destination.updated_at = now
    config = active_workflow()
    if config and config.destination_playlist_id == move.destination_playlist_id:
        membership = db.session.get(LibraryWatchedMembership, move.video_url_id)
        if membership is None:
            membership = LibraryWatchedMembership(video_url_id=move.video_url_id)
            db.session.add(membership)
        membership.confirmed_at = now


def complete(move):
    # Both upstream facts are confirmed before the catalog and receipt commit.
    Video.query.filter_by(id=move.source_entry_id, playlist_id=move.source_playlist_id).delete()
    source = db.session.get(Playlist, move.source_playlist_id)
    if source:
        source.updated_at = datetime.now(timezone.utc)
    commit_stage(move, "done", "succeeded")


def reconcile(service, move):
    """Read-only upstream reconciliation, including after process death."""
    require_access(service, move)
    destination = destination_entry(service, move)
    source = source_entry(service, move)
    move.last_checked_at = datetime.now(timezone.utc)
    if destination:
        save_destination(move, destination)
        if source is None:
            complete(move)
        else:
            commit_stage(move, move.stage, "partial", "Saved to watched; still in added. Confirm removal to finish.")
    elif move.stage == "checking":
        commit_stage(move, move.stage, "failed", "The move stopped before any YouTube change. Refresh and try again.")
    else:
        commit_stage(move, move.stage, "unknown", "YouTube has not confirmed the destination. The move will not be sent again automatically. Check both playlists before taking further action.")


def failed_attempt(move, error):
    db.session.rollback()
    # Do not let a worker whose lock died overwrite a recovering worker's result.
    assert_import_lock()
    db.session.refresh(move)
    current_app.logger.warning("Library move stopped: %s (%s)", move.id, type(error).__name__)
    if move.stage == "checking":
        commit_stage(move, move.stage, "failed", "Couldn’t verify the playlists. No YouTube change was sent. Check the connection and try again.")
    else:
        commit_stage(move, move.stage, "unknown", "Waiting for YouTube confirmation. No request will be repeated automatically.")


def move_video(user, request_id, entry_id, version):
    require_owner(user)
    with import_lock() as acquired:
        if not acquired:
            raise WorkflowError("Another Library sync or move is running. Check its status before trying again.")
        recover_interrupted_runs()
        existing = db.session.get(LibraryMove, request_id)
        if existing:
            if existing.owner_id != user.id or existing.source_entry_id != entry_id:
                raise WorkflowError("This request ID belongs to a different move.")
            return serialize_move(existing)
        config = active_workflow()
        connection = db.session.get(YouTubeConnection, 1)
        if not config or config.version != version or WRITE_SCOPE not in (connection.granted_scopes or []):
            raise WorkflowError("Playlist setup or permissions changed. Refresh before moving a video.")
        existing = LibraryMove.query.filter(
            LibraryMove.channel_id == config.channel_id, LibraryMove.source_entry_id == entry_id,
            LibraryMove.status != "failed",
        ).order_by(LibraryMove.started_at.desc()).first()
        if existing:
            if existing.owner_id != user.id:
                raise WorkflowError("An earlier owner’s move needs reconciliation before this entry can be changed.")
            return serialize_move(existing)
        video = db.session.get(Video, entry_id)
        if video is None or video.playlist_id != config.source_playlist_id or not video.video_url_id:
            raise WorkflowError("This entry is not in the configured added playlist. Refresh the playlist.", 400)
        move = LibraryMove(id=request_id, owner_id=user.id, channel_id=config.channel_id,
            source_playlist_id=config.source_playlist_id, destination_playlist_id=config.destination_playlist_id,
            source_entry_id=entry_id, video_url_id=video.video_url_id, video_title=video.title,
            source_title=db.session.get(Playlist, config.source_playlist_id).title,
            destination_title=db.session.get(Playlist, config.destination_playlist_id).title,
            status="running", stage="checking", started_at=datetime.now(timezone.utc), updated_at=datetime.now(timezone.utc))
        db.session.add(move)
        commit_stage(move, "checking")
        try:
            with get_youtube_service(timeout=15) as service:
                require_access(service, move)
                if source_entry(service, move) is None:
                    raise WorkflowError("The source entry is no longer in YouTube.")
                destination = destination_entry(service, move)
                if destination is None:
                    commit_stage(move, "inserting")
                    assert_import_lock()
                    try:
                        service.playlistItems().insert(part="snippet", body={"snippet": {
                            "playlistId": move.destination_playlist_id,
                            "resourceId": {"kind": "youtube#video", "videoId": move.video_url_id},
                        }}).execute(num_retries=0)
                    except HttpError as error:
                        # Only an explicit rejection of THIS insert proves it
                        # was not accepted. A later status read failing with
                        # 401/403 must never make an ambiguous insert retryable.
                        if error.resp.status in (400, 401, 403, 404):
                            commit_stage(move, "inserting", "failed", "YouTube rejected the addition. The source was kept. Check access or quota before trying again.")
                            return serialize_move(move)
                        raise
                    commit_stage(move, "confirming")
                    destination = destination_entry(service, move)
                if destination is None:
                    commit_stage(move, move.stage, "unknown", "The addition has not been confirmed. The source was kept; check status before taking further action.")
                else:
                    save_destination(move, destination)
                    if source_entry(service, move) is not None:
                        commit_stage(move, "removing")
                        assert_import_lock()
                        service.playlistItems().delete(id=move.source_entry_id).execute(num_retries=0)
                    reconcile(service, move)
        except Exception as error:
            failed_attempt(move, error)
        return serialize_move(move)


def retry_removal(user, move_id, request_id):
    require_owner(user)
    with import_lock() as acquired:
        if not acquired:
            raise WorkflowError("Library is busy. Check the move’s status before retrying.")
        db.session.expire_all()
        require_owner(user)
        move = db.session.get(LibraryMove, move_id)
        if not move or move.owner_id != user.id:
            raise WorkflowError("Move not found.", 404)
        if move.removal_request_id == request_id or move.status == "succeeded":
            return serialize_move(move)
        if move.status != "partial":
            raise WorkflowError("Check the move’s status before retrying removal.")
        move.removal_request_id = request_id
        commit_stage(move, "removing")
        try:
            with get_youtube_service(timeout=15) as service:
                require_access(service, move)
                destination = destination_entry(service, move)
                if destination is None:
                    commit_stage(move, move.stage, "unknown", "The video is no longer confirmed in watched. The source was kept.")
                else:
                    save_destination(move, destination)
                    if source_entry(service, move) is not None:
                        commit_stage(move, "removing")
                        assert_import_lock()
                        service.playlistItems().delete(id=move.source_entry_id).execute(num_retries=0)
                    reconcile(service, move)
        except Exception as error:
            failed_attempt(move, error)
        return serialize_move(move)


def move_status(user, move_id=None):
    require_owner(user)
    query = LibraryMove.query.filter_by(owner_id=user.id)
    if move_id:
        rows = query.filter_by(id=move_id).all()
        if not rows:
            raise WorkflowError("Move not found.", 404)
    else:
        outstanding = query.filter(LibraryMove.status.in_(UNRESOLVED)).order_by(LibraryMove.started_at.desc()).all()
        recent = query.filter(~LibraryMove.status.in_(UNRESOLVED)).order_by(LibraryMove.started_at.desc()).limit(10).all()
        rows = sorted(outstanding + recent, key=lambda move: move.started_at, reverse=True)
    # Reconcile at most one outstanding receipt per poll. No provider writes on
    # status reads; repeated refresh cannot duplicate inserts or remove entries.
    with import_lock() as acquired:
        if acquired:
            db.session.expire_all()
            require_owner(user)
            # Keep older unresolved moves progressing even after polling backs
            # off; repeatedly checking only the newest would starve the rest.
            for move in sorted(rows, key=lambda value: iso(value.last_checked_at) or ""):
                checked = move.last_checked_at
                age = (datetime.now(timezone.utc) - (checked.replace(tzinfo=timezone.utc) if checked and not checked.tzinfo else checked)).total_seconds() if checked else 999
                if move.status in UNRESOLVED and age >= 5:
                    try:
                        with get_youtube_service(timeout=15) as service:
                            reconcile(service, move)
                    except Exception as error:
                        failed_attempt(move, error)
                        move.last_checked_at = datetime.now(timezone.utc)
                        assert_import_lock()
                        db.session.commit()
                    break
        return {"moves": [serialize_move(move) for move in rows], "busy": not acquired}
