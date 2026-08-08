"""Business logic for list management."""

from __future__ import annotations

from typing import Any

from project.models import (
    CustomList,
    ListCategory,
    ListInvitation,
    ListItem,
    User,
    db,
)

ALLOWED_COMPLETED_DISPLAY_MODES = {
    "inline_bottom",
    "category_section",
    "global_section",
}


def get_user_lists(user: User) -> tuple[list[CustomList], list[CustomList]]:
    """Return lists owned by user and lists shared with user."""
    my_lists = CustomList.query.filter_by(owner_id=user.id).all()
    shared_lists = user.shared_lists.all()
    return my_lists, shared_lists


def create_list(owner: User, title: str) -> CustomList:
    """Create and persist a new list."""
    custom_list = CustomList(title=title, owner=owner)
    db.session.add(custom_list)
    db.session.commit()
    return custom_list


def get_list_or_404(list_id: int) -> CustomList:
    """Fetch a list or raise 404."""
    return CustomList.query.get_or_404(list_id)


def get_list_item_or_404(item_id: int) -> ListItem:
    """Fetch a list item or raise 404."""
    return ListItem.query.get_or_404(item_id)


def get_invitation_or_404(token: str) -> ListInvitation:
    """Fetch invitation by token or raise 404."""
    return ListInvitation.query.filter_by(token=token).first_or_404()


def ensure_list_access(custom_list: CustomList, user: User) -> None:
    """Ensure a user can access a list."""
    if custom_list.owner_id != user.id and user not in custom_list.shared_with:
        raise PermissionError("You don't have access to this list.")


def ensure_list_owner(custom_list: CustomList, user: User) -> None:
    """Ensure a user is the list owner."""
    if custom_list.owner_id != user.id:
        raise PermissionError("Only the list owner can perform this action.")


def share_list_with_email(
    *,
    custom_list: CustomList,
    owner: User,
    email: str,
) -> dict[str, Any]:
    """Share a list with an existing user or create a pending invitation."""
    if custom_list.owner_id != owner.id:
        raise PermissionError("You can only share lists you own.")

    cleaned_email = email.strip().lower()
    if not cleaned_email:
        raise ValueError("Please provide an email address.")

    if cleaned_email == owner.email.lower():
        raise ValueError("You can't share a list with yourself.")

    user_to_share_with = User.query.filter_by(email=cleaned_email).first()
    if user_to_share_with:
        if user_to_share_with in custom_list.shared_with:
            return {"status": "already_shared", "email": cleaned_email}

        custom_list.shared_with.append(user_to_share_with)
        db.session.commit()
        return {"status": "shared_existing_user", "email": cleaned_email}

    existing_invitation = (
        ListInvitation.query.filter_by(email=cleaned_email, list_id=custom_list.id)
        .filter(ListInvitation.accepted_at.is_(None))
        .first()
    )
    if existing_invitation and not existing_invitation.is_expired:
        return {"status": "invitation_exists", "email": cleaned_email}

    invitation = ListInvitation.create_invitation(email=cleaned_email, list_id=custom_list.id)
    db.session.add(invitation)
    db.session.commit()
    return {
        "status": "invitation_created",
        "email": cleaned_email,
        "invitation": invitation,
    }


def add_category(*, custom_list: CustomList, name: str) -> ListCategory:
    """Create and append a category to the end of the list."""
    max_order = (
        db.session.query(db.func.max(ListCategory.ordering))
        .filter_by(custom_list_id=custom_list.id)
        .scalar()
        or 0
    )
    category = ListCategory(name=name, custom_list=custom_list, ordering=max_order + 1)
    db.session.add(category)
    db.session.commit()
    return category


def add_item(
    *,
    custom_list_id: int,
    name: str,
    quantity: str | None,
    notes: str | None,
    category_id_raw: str | None,
) -> ListItem:
    """Create and append an item to the end of a category."""
    try:
        category_id = int(category_id_raw)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Invalid category ID: {category_id_raw}") from exc

    category = ListCategory.query.filter_by(
        id=category_id,
        custom_list_id=custom_list_id,
    ).first_or_404()

    max_order = (
        db.session.query(db.func.max(ListItem.ordering))
        .filter_by(category_id=category.id)
        .scalar()
        or 0
    )

    item = ListItem(
        name=name,
        quantity=quantity,
        notes=notes,
        category=category,
        ordering=max_order + 1,
    )
    db.session.add(item)
    db.session.commit()
    return item


def accept_invitation_for_user(invitation: ListInvitation, user: User) -> CustomList:
    """Accept a valid invitation for an authenticated user."""
    if user.email.lower() != invitation.email.lower():
        raise PermissionError(
            f"This invitation was sent to {invitation.email}. "
            "Please log in with that email address."
        )

    custom_list = invitation.custom_list
    if user not in custom_list.shared_with:
        custom_list.shared_with.append(user)

    invitation.accept()
    db.session.commit()
    return custom_list


def update_completed_display_mode(
    *,
    custom_list: CustomList,
    completed_display_mode: str | None,
) -> None:
    """Update list completed item display mode."""
    if completed_display_mode not in ALLOWED_COMPLETED_DISPLAY_MODES:
        raise ValueError("Invalid display mode.")

    custom_list.completed_display_mode = completed_display_mode
    db.session.commit()


def toggle_item_completion(*, item: ListItem, user: User) -> bool:
    """Toggle item completed flag for an authorized user."""
    ensure_list_access(item.category.custom_list, user)
    item.completed = not item.completed
    db.session.commit()
    return item.completed


def reorder_items(
    *,
    custom_list: CustomList,
    user: User,
    items_payload: list[dict[str, Any]],
) -> None:
    """Apply item ordering/category changes for an authorized list user."""
    ensure_list_access(custom_list, user)
    for item_data in items_payload:
        item = ListItem.query.get(item_data["id"])
        if item and item.category.custom_list_id == custom_list.id:
            item.ordering = item_data.get("ordering", item.ordering)
            new_category_id = item_data.get("category_id")
            if new_category_id and ListCategory.query.filter_by(
                id=new_category_id,
                custom_list_id=custom_list.id,
            ).first():
                item.category_id = new_category_id
    db.session.commit()


def reorder_categories(
    *,
    custom_list: CustomList,
    user: User,
    categories_payload: list[dict[str, Any]],
) -> None:
    """Apply category ordering changes for an authorized list user."""
    ensure_list_access(custom_list, user)
    for category_data in categories_payload:
        category = ListCategory.query.get(category_data["id"])
        if category and category.custom_list_id == custom_list.id:
            category.ordering = category_data.get("ordering", category.ordering)
    db.session.commit()


def get_list_debug_payload(*, custom_list: CustomList, user: User) -> dict[str, Any]:
    """Build debug payload for list, categories, and items."""
    ensure_list_access(custom_list, user)
    categories = ListCategory.query.filter_by(custom_list_id=custom_list.id).all()

    debug_data: dict[str, Any] = {
        "list_title": custom_list.title,
        "categories": [],
    }

    for category in categories:
        category_payload = {
            "id": category.id,
            "name": category.name,
            "ordering": category.ordering,
            "items": [],
        }

        items = ListItem.query.filter_by(category_id=category.id).all()
        for item in items:
            category_payload["items"].append(
                {
                    "id": item.id,
                    "name": item.name,
                    "quantity": item.quantity,
                    "notes": item.notes,
                    "completed": item.completed,
                    "ordering": item.ordering,
                }
            )

        debug_data["categories"].append(category_payload)

    return debug_data

