"""JSON wishlist endpoints for API clients."""

from __future__ import annotations

from typing import Any

from flask import Blueprint, jsonify, request
from flask_jwt_extended import get_jwt_identity, jwt_required

from project.database import db
from project.models import User
from project.services import wishlist_service

wishlist_api_blueprint = Blueprint("api_wishlist", __name__, url_prefix="/wishlist")


def _current_user_from_jwt() -> User | None:
    identity = get_jwt_identity()
    if identity is None:
        return None
    try:
        return db.session.get(User, int(identity))
    except (TypeError, ValueError):
        return None


def _request_payload() -> dict[str, Any]:
    if request.is_json:
        return request.get_json(silent=True) or {}
    return request.form.to_dict(flat=True)


@wishlist_api_blueprint.get("/gifts")
@jwt_required()
def api_get_gifts():
    user = _current_user_from_jwt()
    if user is None:
        return jsonify({"error": "Unauthorized."}), 401

    gifts = wishlist_service.list_gifts_for_user(user.id)
    return jsonify({"gifts": [wishlist_service.serialize_gift(gift) for gift in gifts]}), 200


@wishlist_api_blueprint.post("/gifts")
@jwt_required()
def api_create_gift():
    user = _current_user_from_jwt()
    if user is None:
        return jsonify({"error": "Unauthorized."}), 401

    payload = _request_payload()
    try:
        gift = wishlist_service.create_gift_for_user(
            user=user,
            title=payload.get("title", ""),
            body=payload.get("body", ""),
            image_file=request.files.get("image"),
        )
    except wishlist_service.ValidationError:
        return jsonify({"error": "title and body are required"}), 400

    return jsonify({"gift": wishlist_service.serialize_gift(gift)}), 201


@wishlist_api_blueprint.get("/gifts/<int:gift_id>")
@jwt_required()
def api_get_gift(gift_id: int):
    user = _current_user_from_jwt()
    if user is None:
        return jsonify({"error": "Unauthorized."}), 401

    gift = wishlist_service.get_gift_for_user(user_id=user.id, gift_id=gift_id)
    if gift is None:
        return jsonify({"error": "Gift not found."}), 404
    return jsonify({"gift": wishlist_service.serialize_gift(gift)}), 200


@wishlist_api_blueprint.put("/gifts/<int:gift_id>")
@jwt_required()
def api_update_gift(gift_id: int):
    user = _current_user_from_jwt()
    if user is None:
        return jsonify({"error": "Unauthorized."}), 401

    gift = wishlist_service.get_gift_for_user(user_id=user.id, gift_id=gift_id)
    if gift is None:
        return jsonify({"error": "Gift not found."}), 404

    payload = _request_payload()
    title = payload.get("title")
    body = payload.get("body")

    try:
        gift = wishlist_service.update_gift(
            gift=gift,
            title=title,
            body=body,
            image_file=request.files.get("image"),
        )
    except wishlist_service.EmptyTitleError:
        return jsonify({"error": "title cannot be empty"}), 400
    except wishlist_service.EmptyBodyError:
        return jsonify({"error": "body cannot be empty"}), 400
    except wishlist_service.ValidationError:
        return jsonify({"error": "Invalid gift data."}), 400

    return jsonify({"gift": wishlist_service.serialize_gift(gift)}), 200


@wishlist_api_blueprint.delete("/gifts/<int:gift_id>")
@jwt_required()
def api_delete_gift(gift_id: int):
    user = _current_user_from_jwt()
    if user is None:
        return jsonify({"error": "Unauthorized."}), 401

    gift = wishlist_service.get_gift_for_user(user_id=user.id, gift_id=gift_id)
    if gift is None:
        return jsonify({"error": "Gift not found."}), 404

    wishlist_service.delete_gift(gift)
    return jsonify({"message": "Gift deleted."}), 200
