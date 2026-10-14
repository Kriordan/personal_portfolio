"""Account-owned Library shortcuts, independent of imports and sort order."""
from datetime import datetime, timezone

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from project.database import db
from project.models import LibraryPin, Playlist
from project.services.library_service import NotFoundError


def list_pins(user_id):
    pins = LibraryPin.query.filter_by(user_id=user_id).order_by(LibraryPin.pinned_at, LibraryPin.playlist_id).all()
    return [{"playlist_id": pin.playlist_id, "pinned_at": pin.pinned_at.isoformat()} for pin in pins]


def set_pin(user_id, playlist_id, pinned):
    if db.session.get(Playlist, playlist_id) is None:
        raise NotFoundError("Playlist not found.")
    if pinned:
        # A simultaneous request from another device must not duplicate or
        # reorder an existing pin. Both supported databases implement this.
        insert = sqlite_insert if db.engine.dialect.name == "sqlite" else pg_insert
        db.session.execute(insert(LibraryPin).values(
            user_id=user_id, playlist_id=playlist_id, pinned_at=datetime.now(timezone.utc),
        ).on_conflict_do_nothing(index_elements=["user_id", "playlist_id"]))
    else:
        LibraryPin.query.filter_by(user_id=user_id, playlist_id=playlist_id).delete()
    db.session.commit()
    return list_pins(user_id)
