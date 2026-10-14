"""Owner-managed, channel-bound playlist configuration and watched membership."""
from datetime import datetime, timezone
from uuid import uuid4

from project.database import db
from project.library.credentials import WRITE_SCOPE
from project.library.jobs import fetch_videos, get_youtube_service
from project.library.sync_tracking import assert_import_lock, import_lock
from project.models import LibraryWatchedMembership, LibraryWorkflow, Playlist, YouTubeConnection


class WorkflowError(Exception):
    def __init__(self, message, status=409):
        super().__init__(message)
        self.status = status


def connected_owner(user):
    connection = db.session.get(YouTubeConnection, 1)
    return bool(user and user.is_admin and connection and connection.connected_by_id == user.id)


def active_workflow():
    config = db.session.get(LibraryWorkflow, 1)
    connection = db.session.get(YouTubeConnection, 1)
    if (config and connection and config.channel_id == connection.channel_id
            and config.owner_id == connection.connected_by_id):
        return config
    return None


def workflow_status(user):
    config = active_workflow()
    connection = db.session.get(YouTubeConnection, 1)
    owner = connected_owner(user)
    writable = bool(connection and WRITE_SCOPE in (connection.granted_scopes or []))
    source = db.session.get(Playlist, config.source_playlist_id) if config else None
    destination = db.session.get(Playlist, config.destination_playlist_id) if config else None
    reason = None if config and writable else (
        "The connected owner needs to enable playlist changes on the YouTube connection page."
        if not writable else "The connected owner needs to choose the added and watched playlists on the YouTube connection page.")
    return {"is_owner": owner, "can_move": bool(owner and writable and config), "reason": reason,
            "version": config.version if config else None,
            "source": {"id": source.id, "title": source.title} if source else None,
            "destination": {"id": destination.id, "title": destination.title} if destination else None,
            "membership_checked_at": iso(config.membership_checked_at) if config else None}


def iso(value):
    return (value.replace(tzinfo=timezone.utc) if value and not value.tzinfo else value).isoformat() if value else None


def channel_id(service):
    channels = service.channels().list(part="id", mine=True, maxResults=2).execute().get("items", [])
    if len(channels) != 1 or not channels[0].get("id"):
        raise WorkflowError("Choose one YouTube channel when reconnecting.")
    return channels[0]["id"]


def owned_playlists(service, channel, ids):
    # Only ordinary custom playlists, excluding special uploads/likes/watch
    # history IDs whose edit semantics differ or are unsupported by the API.
    if len(ids) != 2 or len(set(ids)) != 2 or any(not value.startswith("PL") or len(value) > 255 for value in ids):
        raise WorkflowError("Choose two different custom playlists owned by the connected channel.", 400)
    items = service.playlists().list(part="snippet", id=",".join(ids), maxResults=50).execute().get("items", [])
    found = {item["id"]: item for item in items}
    if set(found) != set(ids) or any(item["snippet"].get("channelId") != channel for item in items):
        raise WorkflowError("Both playlists must belong to the connected YouTube channel.", 400)
    return found


def replace_membership(items, config):
    """Caller commits only after a complete, successful provider fetch/import."""
    ids = {item.get("contentDetails", {}).get("videoId") or item.get("snippet", {}).get("resourceId", {}).get("videoId") for item in items}
    now = datetime.now(timezone.utc)
    LibraryWatchedMembership.query.delete(synchronize_session=False)
    db.session.add_all([LibraryWatchedMembership(video_url_id=video_id, confirmed_at=now) for video_id in ids if video_id])
    config.membership_checked_at = now


def watched_ids():
    if not active_workflow():
        return set()
    return {row.video_url_id for row in LibraryWatchedMembership.query.all()}


def configure_workflow(user, source_id, destination_id):
    if not connected_owner(user):
        raise WorkflowError("Only the connected administrator can configure playlist moves.", 403)
    with import_lock() as acquired:
        if not acquired:
            raise WorkflowError("Library is busy. Try again when the current operation finishes.")
        db.session.expire_all()
        if not connected_owner(user):
            raise WorkflowError("The connected owner changed. Reload before continuing.", 403)
        connection = db.session.get(YouTubeConnection, 1)
        if WRITE_SCOPE not in (connection.granted_scopes or []):
            raise WorkflowError("Enable playlist changes through Google before choosing the playlists.")
        with get_youtube_service(timeout=15) as service:
            channel = channel_id(service)
            if channel != connection.channel_id:
                raise WorkflowError("The YouTube channel changed. Reconnect and configure the playlists again.")
            items = owned_playlists(service, channel, [source_id, destination_id])
            membership = fetch_videos(destination_id, service)
        config = db.session.get(LibraryWorkflow, 1)
        if config is None:
            config = LibraryWorkflow(id=1)
        for playlist_id, item in items.items():
            if db.session.get(Playlist, playlist_id) is None:
                raise WorkflowError("Sync the Library before choosing these playlists.", 400)
            db.session.get(Playlist, playlist_id).title = item["snippet"]["title"]
        config.version = str(uuid4())
        config.owner_id, config.channel_id = user.id, channel
        config.source_playlist_id, config.destination_playlist_id = source_id, destination_id
        db.session.add(config)
        replace_membership(membership, config)
        assert_import_lock()
        db.session.commit()
        return workflow_status(user)
