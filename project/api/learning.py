"""JSON learning endpoints for API clients."""

from __future__ import annotations

from flask import Blueprint, current_app, jsonify, request
from flask_jwt_extended import get_jwt_identity, jwt_required

from project.database import db
from project.models import User
from project.services import learning_service

learning_api_blueprint = Blueprint("api_learning", __name__, url_prefix="/learning")


def _current_user_from_jwt() -> User | None:
    identity = get_jwt_identity()
    if identity is None:
        return None
    try:
        return db.session.get(User, int(identity))
    except (TypeError, ValueError):
        return None


@learning_api_blueprint.get("/notes")
@jwt_required()
def api_get_notes():
    user = _current_user_from_jwt()
    if user is None:
        return jsonify({"error": "Unauthorized."}), 401

    notes_dir = learning_service.notes_dir_for_root(current_app.root_path)
    notes = learning_service.load_notes(notes_dir)
    notes, total_due = learning_service.summarize_notes_for_user(notes, user_id=user.id)
    return jsonify({"notes": notes, "total_due": total_due}), 200


@learning_api_blueprint.get("/notes/<string:note_id>")
@jwt_required()
def api_get_note(note_id: str):
    user = _current_user_from_jwt()
    if user is None:
        return jsonify({"error": "Unauthorized."}), 401

    notes_dir = learning_service.notes_dir_for_root(current_app.root_path)
    try:
        note_data = learning_service.note_with_cards(notes_dir, note_id)
    except learning_service.NotFoundError:
        return jsonify({"error": "Note not found."}), 404
    return jsonify({"note": note_data}), 200


@learning_api_blueprint.get("/review")
@jwt_required()
def api_get_review():
    user = _current_user_from_jwt()
    if user is None:
        return jsonify({"error": "Unauthorized."}), 401

    notes_dir = learning_service.notes_dir_for_root(current_app.root_path)
    notes = learning_service.load_notes(notes_dir)
    due_cards = learning_service.review_cards_for_user(notes, user_id=user.id)
    return jsonify({"cards": due_cards}), 200


@learning_api_blueprint.post("/rate")
@jwt_required()
def api_rate_card():
    user = _current_user_from_jwt()
    if user is None:
        return jsonify({"error": "Unauthorized."}), 401

    payload = request.get_json(silent=True) or {}
    card_id = payload.get("card_id")
    rating = payload.get("rating")
    response_ms = payload.get("response_ms")
    session_id = payload.get("session_id")

    if not card_id or rating is None:
        return jsonify({"error": "card_id and rating are required"}), 400
    try:
        rating = int(rating)
    except (TypeError, ValueError):
        return jsonify({"error": "rating must be an integer"}), 400
    notes_dir = learning_service.notes_dir_for_root(current_app.root_path)
    try:
        response_data = learning_service.rate_card_for_user(
            user=user,
            notes_dir=notes_dir,
            card_id=card_id,
            rating=rating,
            response_ms=response_ms,
            session_id=session_id,
        )
    except learning_service.InvalidRatingError:
        return jsonify({"error": "rating must be between 0 and 5"}), 400
    except learning_service.InvalidCardIdError:
        return jsonify({"error": "invalid card_id format"}), 400
    except learning_service.ValidationError:
        return jsonify({"error": "Invalid review request."}), 400
    except learning_service.NotFoundError:
        return jsonify({"error": "card not found"}), 404
    return jsonify(response_data), 200
