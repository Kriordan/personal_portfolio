"""
WebSocket event handlers for real-time list collaboration.

This module handles all Socket.IO events for the lists feature, including:
- User joining/leaving list rooms
- Broadcasting item toggles, additions, and reorders
- Broadcasting category changes
- Settings updates
"""

from flask import request
from flask_login import current_user
from flask_socketio import SocketIO, emit, join_room, leave_room

from project.models import CustomList

# Initialize SocketIO instance - configured in __init__.py via register_websockets()
socketio = SocketIO()


def register_handlers():
    """Register all Socket.IO event handlers."""

    @socketio.on("connect")
    def handle_connect():
        """Handle client connection."""
        if not current_user.is_authenticated:
            return False  # Reject unauthenticated connections
        print(f"Client connected: {request.sid}")
        return True

    @socketio.on("disconnect")
    def handle_disconnect():
        """Handle client disconnection."""
        print(f"Client disconnected: {request.sid}")

    @socketio.on("join_list")
    def handle_join_list(data):
        """
        Handle a user joining a list room.

        Args:
            data: Dict containing 'list_id'
        """
        if not current_user.is_authenticated:
            return {"success": False, "error": "Not authenticated"}

        list_id = data.get("list_id")
        if not list_id:
            return {"success": False, "error": "No list_id provided"}

        custom_list = CustomList.query.get(list_id)
        if not custom_list:
            return {"success": False, "error": "List not found"}

        if (
            custom_list.owner_id != current_user.id
            and current_user not in custom_list.shared_with
        ):
            return {"success": False, "error": "Access denied"}

        room = f"list_{list_id}"
        join_room(room)
        print(f"User {current_user.username} joined room {room}")

        emit(
            "user_joined",
            {
                "user_id": current_user.id,
                "username": current_user.username,
            },
            room=room,
            include_self=False,
        )

        return {"success": True, "room": room}

    @socketio.on("leave_list")
    def handle_leave_list(data):
        """
        Handle a user leaving a list room.

        Args:
            data: Dict containing 'list_id'
        """
        list_id = data.get("list_id")
        if list_id:
            room = f"list_{list_id}"
            leave_room(room)
            print(f"User {current_user.username} left room {room}")

            emit(
                "user_left",
                {
                    "user_id": current_user.id,
                    "username": current_user.username,
                },
                room=room,
                include_self=False,
            )

    @socketio.on("item_toggled")
    def handle_item_toggled(data):
        """
        Broadcast when an item's completed status is toggled.

        Args:
            data: Dict containing 'list_id', 'item_id', 'completed'
        """
        list_id = data.get("list_id")
        if not list_id:
            return

        room = f"list_{list_id}"
        emit(
            "item_toggled",
            {
                "list_id": list_id,
                "item_id": data.get("item_id"),
                "completed": data.get("completed"),
                "toggled_by": current_user.username,
            },
            room=room,
            include_self=False,
        )

    @socketio.on("item_added")
    def handle_item_added(data):
        """
        Broadcast when a new item is added.

        Args:
            data: Dict containing 'list_id', 'category_id', 'item' details
        """
        list_id = data.get("list_id")
        if not list_id:
            return

        room = f"list_{list_id}"
        emit(
            "item_added",
            {
                "list_id": list_id,
                "category_id": data.get("category_id"),
                "item": data.get("item"),
                "added_by": current_user.username,
            },
            room=room,
            include_self=False,
        )

    @socketio.on("items_reordered")
    def handle_items_reordered(data):
        """
        Broadcast when items are reordered.

        Args:
            data: Dict containing 'list_id', 'items' (list of item order data)
        """
        list_id = data.get("list_id")
        if not list_id:
            return

        room = f"list_{list_id}"
        emit(
            "items_reordered",
            {
                "list_id": list_id,
                "items": data.get("items"),
                "reordered_by": current_user.username,
            },
            room=room,
            include_self=False,
        )

    @socketio.on("category_added")
    def handle_category_added(data):
        """
        Broadcast when a new category is added.

        Args:
            data: Dict containing 'list_id', 'category' details
        """
        list_id = data.get("list_id")
        if not list_id:
            return

        room = f"list_{list_id}"
        emit(
            "category_added",
            {
                "list_id": list_id,
                "category": data.get("category"),
                "added_by": current_user.username,
            },
            room=room,
            include_self=False,
        )

    @socketio.on("categories_reordered")
    def handle_categories_reordered(data):
        """
        Broadcast when categories are reordered.

        Args:
            data: Dict containing 'list_id', 'categories' (list of category order data)
        """
        list_id = data.get("list_id")
        if not list_id:
            return

        room = f"list_{list_id}"
        emit(
            "categories_reordered",
            {
                "list_id": list_id,
                "categories": data.get("categories"),
                "reordered_by": current_user.username,
            },
            room=room,
            include_self=False,
        )

    @socketio.on("settings_updated")
    def handle_settings_updated(data):
        """
        Broadcast when list settings are updated.

        Args:
            data: Dict containing 'list_id' and updated settings
        """
        list_id = data.get("list_id")
        if not list_id:
            return

        room = f"list_{list_id}"
        emit(
            "settings_updated",
            {
                "list_id": list_id,
                "completed_display_mode": data.get("completed_display_mode"),
                "updated_by": current_user.username,
            },
            room=room,
            include_self=False,
        )


def broadcast_to_list(list_id, event, data):
    """
    Utility function to broadcast an event to all users viewing a specific list.

    Can be called from views to broadcast events.

    Args:
        list_id: The ID of the list
        event: The event name to emit
        data: The data to send with the event
    """
    room = f"list_{list_id}"
    socketio.emit(event, data, room=room)
