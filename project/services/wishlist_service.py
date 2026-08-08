"""Business logic shared by wishlist web and API routes."""

from __future__ import annotations

import os

import boto3
from botocore.exceptions import NoCredentialsError

from project.database import db
from project.models import Gift, User


class WishlistServiceError(Exception):
    """Base wishlist service exception."""


class ValidationError(WishlistServiceError):
    """Raised when service input fails validation."""


class EmptyTitleError(ValidationError):
    """Raised when an update would leave a gift title empty."""


class EmptyBodyError(ValidationError):
    """Raised when an update would leave a gift body empty."""


def serialize_gift(gift: Gift) -> dict[str, object]:
    """Return a JSON-safe gift payload."""
    return {
        "id": gift.id,
        "title": gift.title,
        "body": gift.body,
        "image_url": gift.image_url,
        "timestamp": gift.timestamp.isoformat() if gift.timestamp else None,
        "user_id": gift.user_id,
    }


def upload_image_to_s3(file_obj) -> str | None:
    """Upload a file object to S3 and return the public URL."""
    bucket_name = os.getenv("WISHLIST_S3_BUCKET")
    if not bucket_name:
        return None

    s3 = boto3.client("s3")
    try:
        s3.upload_fileobj(file_obj, bucket_name, file_obj.filename)
        return f"https://{bucket_name}.s3.amazonaws.com/{file_obj.filename}"
    except NoCredentialsError:
        return None


def list_gifts_for_user(user_id: int) -> list[Gift]:
    """Return all gifts that belong to the provided user ID."""
    return db.session.execute(db.select(Gift).filter_by(user_id=user_id)).scalars().all()


def get_gift_for_user(*, user_id: int, gift_id: int) -> Gift | None:
    """Return a gift if it belongs to the provided user, otherwise None."""
    gift = db.session.get(Gift, gift_id)
    if gift is None or gift.user_id != user_id:
        return None
    return gift


def create_gift_for_user(
    *,
    user: User,
    title: str,
    body: str,
    image_file=None,
) -> Gift:
    """Create and persist a gift owned by user."""
    cleaned_title = (title or "").strip()
    cleaned_body = (body or "").strip()
    if not cleaned_title or not cleaned_body:
        raise ValidationError("title and body are required")

    gift = Gift(title=cleaned_title, body=cleaned_body, author=user)
    if image_file:
        image_url = upload_image_to_s3(image_file)
        if image_url:
            gift.image_url = image_url

    db.session.add(gift)
    db.session.commit()
    return gift


def update_gift(
    *,
    gift: Gift,
    title: str | None = None,
    body: str | None = None,
    image_file=None,
) -> Gift:
    """Update and persist a gift record."""
    if title is not None:
        cleaned_title = str(title).strip()
        if not cleaned_title:
            raise EmptyTitleError("title cannot be empty")
        gift.title = cleaned_title

    if body is not None:
        cleaned_body = str(body).strip()
        if not cleaned_body:
            raise EmptyBodyError("body cannot be empty")
        gift.body = cleaned_body

    if image_file:
        image_url = upload_image_to_s3(image_file)
        if image_url:
            gift.image_url = image_url

    db.session.commit()
    return gift


def delete_gift(gift: Gift) -> None:
    """Delete a gift record."""
    db.session.delete(gift)
    db.session.commit()
