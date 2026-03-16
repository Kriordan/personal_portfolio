"""JSON library endpoints for API clients."""

from __future__ import annotations

from flask import Blueprint, jsonify
from flask_jwt_extended import get_jwt_identity, jwt_required

from project.database import db
from project.models import User
from project.services import library_service

library_api_blueprint = Blueprint("api_library", __name__, url_prefix="/library")


def _current_user_from_jwt() -> User | None:
    identity = get_jwt_identity()
    if identity is None:
        return None
    try:
        return db.session.get(User, int(identity))
    except (TypeError, ValueError):
        return None

@library_api_blueprint.get("/playlists")
@jwt_required()
def api_get_playlists():
    user = _current_user_from_jwt()
    if user is None:
        return jsonify({"error": "Unauthorized."}), 401

    playlists = library_service.list_playlists()
    return (
        jsonify(
            {
                "playlists": [
                    library_service.serialize_playlist(playlist) for playlist in playlists
                ]
            }
        ),
        200,
    )


@library_api_blueprint.get("/playlists/<string:playlist_id>")
@jwt_required()
def api_get_playlist(playlist_id: str):
    user = _current_user_from_jwt()
    if user is None:
        return jsonify({"error": "Unauthorized."}), 401

    try:
        playlist, videos = library_service.get_playlist_with_videos(playlist_id=playlist_id)
    except library_service.NotFoundError:
        return jsonify({"error": "Playlist not found."}), 404

    return (
        jsonify(
            {
                "playlist": library_service.serialize_playlist(playlist),
                "videos": [library_service.serialize_video(video) for video in videos],
            }
        ),
        200,
    )


@library_api_blueprint.get("/videos/<string:video_id>")
@jwt_required()
def api_get_video(video_id: str):
    user = _current_user_from_jwt()
    if user is None:
        return jsonify({"error": "Unauthorized."}), 401

    try:
        video = library_service.get_video(video_id=video_id)
    except library_service.NotFoundError:
        return jsonify({"error": "Video not found."}), 404
    return jsonify({"video": library_service.serialize_video(video)}), 200


@library_api_blueprint.post("/sync")
@jwt_required()
def api_sync_library():
    user = _current_user_from_jwt()
    if user is None:
        return jsonify({"error": "Unauthorized."}), 401

    library_service.sync_library()
    return jsonify({"message": "Library sync completed."}), 200
