"""JSON library endpoints for API clients."""

from __future__ import annotations

from uuid import UUID

from flask import Blueprint, jsonify, request
from flask_jwt_extended import get_jwt_identity, jwt_required

from project.database import db
from project.models import User
from project.services import library_service
from project.library.sync_tracking import sync_status
from project.services import library_pins
from project.library.workflow import WorkflowError, watched_ids, workflow_status
from project.library.moves import move_status, move_video, retry_removal

library_api_blueprint = Blueprint("api_library", __name__, url_prefix="/library")


@library_api_blueprint.after_request
def private_library_response(response):
    response.headers["Cache-Control"] = "private, no-store"
    return response


@library_api_blueprint.get("/pins")
@jwt_required()
def api_get_pins():
    user = _current_user_from_jwt()
    if user is None:
        return jsonify({"error": "Unauthorized."}), 401
    return jsonify({"pins": library_pins.list_pins(user.id)})


@library_api_blueprint.put("/pins/<string:playlist_id>")
@jwt_required()
def api_set_pin(playlist_id):
    user = _current_user_from_jwt()
    if user is None:
        return jsonify({"error": "Unauthorized."}), 401
    body = request.get_json(silent=True)
    if not isinstance(body, dict) or type(body.get("pinned")) is not bool:
        return jsonify({"error": "A pinned boolean is required."}), 400
    try:
        return jsonify({"pins": library_pins.set_pin(user.id, playlist_id, body["pinned"])})
    except library_service.NotFoundError:
        return jsonify({"error": "Playlist not found."}), 404


def _current_user_from_jwt() -> User | None:
    identity = get_jwt_identity()
    if identity is None:
        return None
    try:
        return db.session.get(User, int(identity))
    except (TypeError, ValueError):
        return None


def _uuid(value):
    try:
        return isinstance(value, str) and str(UUID(value)) == value
    except (ValueError, TypeError, AttributeError):
        return False


@library_api_blueprint.errorhandler(WorkflowError)
def workflow_error(error):
    return jsonify({"error": str(error)}), error.status


@library_api_blueprint.get("/workflow")
@jwt_required()
def api_workflow():
    user = _current_user_from_jwt()
    if user is None:
        return jsonify({"error": "Unauthorized."}), 401
    return jsonify(workflow_status(user))


@library_api_blueprint.route("/moves", methods=["GET", "POST"])
@jwt_required()
def api_moves():
    user = _current_user_from_jwt()
    if user is None:
        return jsonify({"error": "Unauthorized."}), 401
    if request.method == "GET":
        return jsonify(move_status(user))
    body = request.get_json(silent=True)
    if (not isinstance(body, dict) or not _uuid(body.get("request_id"))
            or not _uuid(body.get("workflow_version"))
            or not isinstance(body.get("source_entry_id"), str) or not 0 < len(body["source_entry_id"]) <= 255):
        return jsonify({"error": "A request ID, workflow version and source entry are required."}), 400
    return jsonify({"move": move_video(user, body["request_id"], body["source_entry_id"], body["workflow_version"])})


@library_api_blueprint.get("/moves/<string:move_id>")
@jwt_required()
def api_move_status(move_id):
    user = _current_user_from_jwt()
    if user is None:
        return jsonify({"error": "Unauthorized."}), 401
    if not _uuid(move_id):
        return jsonify({"error": "Invalid move ID."}), 400
    return jsonify(move_status(user, move_id))


@library_api_blueprint.post("/moves/<string:move_id>/retry-removal")
@jwt_required()
def api_retry_removal(move_id):
    user = _current_user_from_jwt()
    if user is None:
        return jsonify({"error": "Unauthorized."}), 401
    body = request.get_json(silent=True)
    if not _uuid(move_id) or not isinstance(body, dict) or not _uuid(body.get("request_id")):
        return jsonify({"error": "Valid move and removal request IDs are required."}), 400
    return jsonify({"move": retry_removal(user, move_id, body["request_id"])})

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

    membership = watched_ids()
    return (
        jsonify(
            {
                "playlist": library_service.serialize_playlist(playlist),
                "videos": [library_service.serialize_video(video, membership=membership) for video in videos],
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
