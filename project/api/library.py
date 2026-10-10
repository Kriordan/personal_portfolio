"""JSON library endpoints for API clients."""

from __future__ import annotations

from uuid import UUID

from flask import Blueprint, jsonify, request
from flask_jwt_extended import get_jwt_identity, jwt_required

from project.database import db
from project.models import User
from project.services import library_service
from project.library.sync_tracking import sync_status

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

    body = request.get_json(silent=True)
    request_id = body.get("request_id") if isinstance(body, dict) else None
    if request_id is not None:
        try:
            if str(UUID(request_id)) != request_id:
                raise ValueError()
        except (ValueError, TypeError, AttributeError):
            return jsonify({"error": "A valid sync request ID is required."}), 400
    try:
        run = library_service.sync_library(request_id=request_id)
    except library_service.SyncError as error:
        return jsonify({"error": str(error)}), error.status
    if request_id:
        return jsonify({"run": run}), 200
    return jsonify({"message": "Library sync completed."}), 200


@library_api_blueprint.get("/sync-status")
@jwt_required()
def api_sync_status():
    if _current_user_from_jwt() is None:
        return jsonify({"error": "Unauthorized."}), 401
    request_id = request.args.get("request_id")
    if request_id and len(request_id) > 36:
        return jsonify({"error": "Invalid sync request ID."}), 400
    response = jsonify(sync_status(request_id))
    response.headers["Cache-Control"] = "private, no-store"
    return response
