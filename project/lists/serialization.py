"""Shared REST and realtime representations of grocery rows."""

from typing import Any

from project.models import ListCategory, ListItem


def serialize_item(item: ListItem) -> dict[str, Any]:
    return {
        "id": item.id,
        "name": item.name,
        "quantity": item.quantity,
        "notes": item.notes,
        "completed": item.completed,
        "ordering": item.ordering,
        "category_id": item.category_id,
    }


def serialize_category(category: ListCategory) -> dict[str, Any]:
    return {
        "id": category.id,
        "name": category.name,
        "ordering": category.ordering,
        "items": [
            serialize_item(item) for item in category.items.order_by(ListItem.ordering.asc()).all()
        ],
    }
