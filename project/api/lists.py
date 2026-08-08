"""JSON list management endpoints for API clients."""

from __future__ import annotations

from typing import Any

from flask import Blueprint, current_app, jsonify, request, url_for
from flask_jwt_extended import get_jwt_identity, jwt_required
from mailersend import EmailBuilder, MailerSendClient
from werkzeug.exceptions import NotFound

from project.database import db
from project.foyer.email_templates import get_list_invitation_email_content
from project.models import CustomList, ListCategory, ListItem, User
from project.services import lists_service

lists_api_blueprint = Blueprint("api_lists", __name__, url_prefix="/lists")


def _current_user_from_jwt() -> User | None:
    identity = get_jwt_identity()
    if identity is None:
        return None
    try:
        return db.session.get(User, int(identity))
    except (TypeError, ValueError):
        return None


def _serialize_item(item: ListItem) -> dict[str, Any]:
    return {
        "id": item.id,
        "name": item.name,
        "quantity": item.quantity,
        "notes": item.notes,
        "completed": item.completed,
        "ordering": item.ordering,
        "category_id": item.category_id,
    }


def _serialize_category(category: ListCategory) -> dict[str, Any]:
    return {
        "id": category.id,
        "name": category.name,
        "ordering": category.ordering,
        "items": [
            _serialize_item(item) for item in category.items.order_by(ListItem.ordering.asc()).all()
        ],
    }


def _serialize_list_summary(custom_list: CustomList) -> dict[str, Any]:
    return {
        "id": custom_list.id,
        "title": custom_list.title,
        "owner_id": custom_list.owner_id,
        "completed_display_mode": custom_list.completed_display_mode,
        "created_at": custom_list.created_at.isoformat() if custom_list.created_at else None,
        "updated_at": custom_list.updated_at.isoformat() if custom_list.updated_at else None,
    }


def _serialize_list_detail(custom_list: CustomList) -> dict[str, Any]:
    payload = _serialize_list_summary(custom_list)
    payload["categories"] = [
        _serialize_category(category)
        for category in custom_list.categories.order_by(ListCategory.ordering.asc()).all()
    ]
    return payload


def _send_list_invitation_email(
    *,
    email: str,
    inviter_name: str,
    list_title: str,
    invite_url: str,
) -> None:
    html_content = get_list_invitation_email_content(inviter_name, list_title, invite_url)
    ms = MailerSendClient(api_key=current_app.config["MAILERSEND_API_KEY"])
    email_message = (
        EmailBuilder()
        .from_email("noreply@keithriordan.com", "Keith Riordan Portfolio")
        .to_many([{"email": email, "name": email.split("@")[0]}])
        .subject(f"{inviter_name} invited you to collaborate on a list")
        .html(html_content)
        .build()
    )
    ms.emails.send(email_message)


@lists_api_blueprint.get("/")
@jwt_required()
def api_get_lists():
    user = _current_user_from_jwt()
    if user is None:
        return jsonify({"error": "Unauthorized."}), 401

    my_lists, shared_lists = lists_service.get_user_lists(user)
    return (
        jsonify(
            {
                "owned": [_serialize_list_summary(custom_list) for custom_list in my_lists],
                "shared": [_serialize_list_summary(custom_list) for custom_list in shared_lists],
            }
        ),
        200,
    )


@lists_api_blueprint.post("/")
@jwt_required()
def api_create_list():
    user = _current_user_from_jwt()
    if user is None:
        return jsonify({"error": "Unauthorized."}), 401

    payload = request.get_json(silent=True) or {}
    title = (payload.get("title") or "").strip()
    if not title:
        return jsonify({"error": "Title is required."}), 400

    custom_list = lists_service.create_list(owner=user, title=title)
    return jsonify({"list": _serialize_list_summary(custom_list)}), 201


@lists_api_blueprint.get("/<int:list_id>")
@jwt_required()
def api_get_list(list_id: int):
    user = _current_user_from_jwt()
    if user is None:
        return jsonify({"error": "Unauthorized."}), 401

    try:
        custom_list = lists_service.get_list_or_404(list_id)
        lists_service.ensure_list_access(custom_list, user)
    except NotFound:
        return jsonify({"error": "List not found."}), 404
    except PermissionError:
        return jsonify({"error": "Access denied."}), 403

    return jsonify({"list": _serialize_list_detail(custom_list)}), 200


@lists_api_blueprint.post("/<int:list_id>/items")
@jwt_required()
def api_add_item(list_id: int):
    user = _current_user_from_jwt()
    if user is None:
        return jsonify({"error": "Unauthorized."}), 401

    try:
        custom_list = lists_service.get_list_or_404(list_id)
        lists_service.ensure_list_access(custom_list, user)
    except NotFound:
        return jsonify({"error": "List not found."}), 404
    except PermissionError:
        return jsonify({"error": "Access denied."}), 403

    payload = request.get_json(silent=True) or {}
    name = (payload.get("name") or "").strip()
    if not name:
        return jsonify({"error": "Item name is required."}), 400

    try:
        item = lists_service.add_item(
            custom_list_id=list_id,
            name=name,
            quantity=payload.get("quantity"),
            notes=payload.get("notes"),
            category_id_raw=str(payload.get("category_id") or ""),
        )
    except ValueError:
        return jsonify({"error": "Invalid category ID."}), 400
    except NotFound:
        return jsonify({"error": "Category not found."}), 404

    return jsonify({"item": _serialize_item(item)}), 201


@lists_api_blueprint.post("/<int:list_id>/items/<int:item_id>/toggle")
@jwt_required()
def api_toggle_item(list_id: int, item_id: int):
    user = _current_user_from_jwt()
    if user is None:
        return jsonify({"error": "Unauthorized."}), 401

    try:
        custom_list = lists_service.get_list_or_404(list_id)
        lists_service.ensure_list_access(custom_list, user)
        item = ListItem.query.get_or_404(item_id)
    except NotFound:
        return jsonify({"error": "List or item not found."}), 404
    except PermissionError:
        return jsonify({"error": "Access denied."}), 403

    if item.category.custom_list_id != custom_list.id:
        return jsonify({"error": "Item not found in this list."}), 404

    completed = lists_service.toggle_item_completion(item=item, user=user)
    return jsonify({"completed": completed}), 200


@lists_api_blueprint.post("/<int:list_id>/items/reorder")
@jwt_required()
def api_reorder_items(list_id: int):
    user = _current_user_from_jwt()
    if user is None:
        return jsonify({"error": "Unauthorized."}), 401

    payload = request.get_json(silent=True) or {}
    items_payload = payload.get("items", [])
    if not isinstance(items_payload, list):
        return jsonify({"error": "items must be an array."}), 400

    try:
        custom_list = lists_service.get_list_or_404(list_id)
        lists_service.reorder_items(
            custom_list=custom_list,
            user=user,
            items_payload=items_payload,
        )
    except NotFound:
        return jsonify({"error": "List not found."}), 404
    except PermissionError:
        return jsonify({"error": "Access denied."}), 403

    return jsonify({"message": "Items reordered."}), 200


@lists_api_blueprint.post("/<int:list_id>/categories")
@jwt_required()
def api_add_category(list_id: int):
    user = _current_user_from_jwt()
    if user is None:
        return jsonify({"error": "Unauthorized."}), 401

    try:
        custom_list = lists_service.get_list_or_404(list_id)
        lists_service.ensure_list_access(custom_list, user)
    except NotFound:
        return jsonify({"error": "List not found."}), 404
    except PermissionError:
        return jsonify({"error": "Access denied."}), 403

    payload = request.get_json(silent=True) or {}
    name = (payload.get("name") or "").strip()
    if not name:
        return jsonify({"error": "Category name is required."}), 400

    category = lists_service.add_category(custom_list=custom_list, name=name)
    return jsonify({"category": _serialize_category(category)}), 201


@lists_api_blueprint.post("/<int:list_id>/categories/reorder")
@jwt_required()
def api_reorder_categories(list_id: int):
    user = _current_user_from_jwt()
    if user is None:
        return jsonify({"error": "Unauthorized."}), 401

    payload = request.get_json(silent=True) or {}
    categories_payload = payload.get("categories", [])
    if not isinstance(categories_payload, list):
        return jsonify({"error": "categories must be an array."}), 400

    try:
        custom_list = lists_service.get_list_or_404(list_id)
        lists_service.reorder_categories(
            custom_list=custom_list,
            user=user,
            categories_payload=categories_payload,
        )
    except NotFound:
        return jsonify({"error": "List not found."}), 404
    except PermissionError:
        return jsonify({"error": "Access denied."}), 403

    return jsonify({"message": "Categories reordered."}), 200


@lists_api_blueprint.post("/<int:list_id>/share")
@jwt_required()
def api_share_list(list_id: int):
    user = _current_user_from_jwt()
    if user is None:
        return jsonify({"error": "Unauthorized."}), 401

    try:
        custom_list = lists_service.get_list_or_404(list_id)
    except NotFound:
        return jsonify({"error": "List not found."}), 404

    payload = request.get_json(silent=True) or {}
    email = payload.get("email") or ""
    try:
        result = lists_service.share_list_with_email(
            custom_list=custom_list,
            owner=user,
            email=email,
        )
    except PermissionError:
        return jsonify({"error": "Only the list owner can share this list."}), 403
    except ValueError:
        return jsonify({"error": "Invalid share request."}), 400

    if result["status"] == "invitation_created":
        invitation = result["invitation"]
        try:
            invite_url = url_for("lists.accept_invitation", token=invitation.token, _external=True)
            _send_list_invitation_email(
                email=result["email"],
                inviter_name=user.username,
                list_title=custom_list.title,
                invite_url=invite_url,
            )
        except Exception:
            current_app.logger.exception("Failed to send invitation email to %s", result["email"])

    response_payload = {"status": result["status"], "email": result["email"]}
    return jsonify(response_payload), 200


@lists_api_blueprint.patch("/<int:list_id>/settings")
@jwt_required()
def api_update_list_settings(list_id: int):
    user = _current_user_from_jwt()
    if user is None:
        return jsonify({"error": "Unauthorized."}), 401

    try:
        custom_list = lists_service.get_list_or_404(list_id)
        lists_service.ensure_list_owner(custom_list, user)
    except NotFound:
        return jsonify({"error": "List not found."}), 404
    except PermissionError:
        return jsonify({"error": "Only the list owner can update settings."}), 403

    payload = request.get_json(silent=True) or {}
    completed_display_mode = payload.get("completed_display_mode")
    try:
        lists_service.update_completed_display_mode(
            custom_list=custom_list,
            completed_display_mode=completed_display_mode,
        )
    except ValueError:
        return jsonify({"error": "Invalid display mode."}), 400

    return jsonify({"list": _serialize_list_summary(custom_list)}), 200
