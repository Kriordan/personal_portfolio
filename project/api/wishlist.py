"""JSON wishlist endpoints for API clients."""

from __future__ import annotations

from typing import Any

from flask import Blueprint, current_app, jsonify, request
from flask_jwt_extended import get_jwt_identity, jwt_required
from werkzeug.exceptions import RequestEntityTooLarge

from project.database import db
from project.models import User
from project.services import wishlist_service

wishlist_api_blueprint = Blueprint("api_wishlist", __name__, url_prefix="/wishlist")


@wishlist_api_blueprint.before_request
def limit_request_size():
    request.max_content_length = wishlist_service.MAX_REQUEST_BYTES


@wishlist_api_blueprint.after_request
def private_response(response):
    response.headers["Cache-Control"] = "private, no-store"
    return response


@wishlist_api_blueprint.errorhandler(RequestEntityTooLarge)
def request_too_large(_error):
    return jsonify({"error": "Photo requests must be 6 MiB or less."}), 413


@wishlist_api_blueprint.errorhandler(wishlist_service.ValidationError)
def validation_failed(error):
    db.session.rollback()
    return jsonify({"error": wishlist_service.validation_message(error)}), 400


@wishlist_api_blueprint.errorhandler(wishlist_service.UploadError)
def upload_failed(error):
    db.session.rollback()
    current_app.logger.exception("Wishlist photo upload failed")
    return jsonify({"error": wishlist_service.UPLOAD_MESSAGE}), 503


def _mutation_failed():
    db.session.rollback()
    current_app.logger.exception("Wishlist persistence failed")
    return jsonify({"error": "Couldn’t save the gift. Try again."}), 500


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
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict):
            raise wishlist_service.ValidationError()
        return payload
    return request.form.to_dict(flat=True)


@wishlist_api_blueprint.get("/gifts")
@jwt_required()
def api_get_gifts():
    user = _current_user_from_jwt()
    if user is None:
        return jsonify({"error": "Unauthorized."}), 401

    gifts = wishlist_service.list_gifts_for_user(user.id)
    return jsonify({"gifts": [wishlist_service.serialize_gift(gift, user_id=user.id) for gift in gifts]}), 200


@wishlist_api_blueprint.post("/gifts")
@jwt_required()
def api_create_gift():
    user = _current_user_from_jwt()
    if user is None:
        return jsonify({"error": "Unauthorized."}), 401

    payload = _request_payload()
    if "remove_image" in payload:
        raise wishlist_service.ValidationError("remove_create")
    try:
        gift = wishlist_service.create_gift_for_user(
            user=user,
            title=payload.get("title", ""),
            body=payload.get("body", ""),
            image_file=request.files.get("image"),
        )
    except wishlist_service.WishlistServiceError:
        raise
    except RequestEntityTooLarge:
        raise
    except Exception:
        return _mutation_failed()

    return jsonify({"gift": wishlist_service.serialize_gift(gift, user_id=user.id)}), 201


@wishlist_api_blueprint.get("/gifts/<int:gift_id>")
@jwt_required()
def api_get_gift(gift_id: int):
    user = _current_user_from_jwt()
    if user is None:
        return jsonify({"error": "Unauthorized."}), 401

    gift = wishlist_service.get_gift_for_user(user_id=user.id, gift_id=gift_id)
    if gift is None:
        return jsonify({"error": "Gift not found."}), 404
    return jsonify({"gift": wishlist_service.serialize_gift(gift, user_id=user.id)}), 200


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
    title = payload.get("title", wishlist_service.UNSET)
    body = payload.get("body", wishlist_service.UNSET)
    remove_image = wishlist_service.parse_remove_image(
        payload.get("remove_image", False), multipart=not request.is_json
    )

    try:
        gift = wishlist_service.update_gift(
            gift=gift,
            title=title,
            body=body,
            image_file=request.files.get("image"),
            remove_image=remove_image,
        )
    except wishlist_service.WishlistServiceError:
        raise
    except RequestEntityTooLarge:
        raise
    except Exception:
        return _mutation_failed()

    return jsonify({"gift": wishlist_service.serialize_gift(gift, user_id=user.id)}), 200


@wishlist_api_blueprint.delete("/gifts/<int:gift_id>")
@jwt_required()
def api_delete_gift(gift_id: int):
    user = _current_user_from_jwt()
    if user is None:
        return jsonify({"error": "Unauthorized."}), 401

    gift = wishlist_service.get_gift_for_user(user_id=user.id, gift_id=gift_id)
    if gift is None:
        return jsonify({"error": "Gift not found."}), 404

    try:
        wishlist_service.delete_gift(gift)
    except Exception:
        return _mutation_failed()
    return jsonify({"message": "Gift deleted."}), 200
