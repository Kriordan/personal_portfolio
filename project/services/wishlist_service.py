"""Business logic shared by Wishlist web and API routes."""

from __future__ import annotations

import io
import os
import warnings
from uuid import uuid4

from boto3.exceptions import S3UploadFailedError
from botocore.exceptions import BotoCoreError, ClientError
from PIL import Image, ImageOps, UnidentifiedImageError

from project.database import db
from project.models import Gift, User
from project import wishlist_storage

MAX_IMAGE_BYTES = 5 * 1024 * 1024
MAX_REQUEST_BYTES = 6 * 1024 * 1024
MAX_IMAGE_PIXELS = 25_000_000
UNSET = object()


class WishlistServiceError(Exception):
    """Base Wishlist service exception."""


class ValidationError(WishlistServiceError):
    """A code, never exception text, selects an application-owned message."""

    def __init__(self, code="invalid"):
        self.code = code
        super().__init__(code)


class EmptyTitleError(ValidationError):
    def __init__(self):
        super().__init__("empty_title")


class EmptyBodyError(ValidationError):
    def __init__(self):
        super().__init__("empty_body")


class UploadError(WishlistServiceError):
    """Storage is unavailable; the requested gift change was not saved."""


VALIDATION_MESSAGES = {
    "required": "title and body are required",
    "empty_title": "title cannot be empty",
    "empty_body": "body cannot be empty",
    "text_type": "Title and description must be text.",
    "text_length": "Title and description must each be 140 characters or fewer.",
    "remove_flag": "remove_image must be true or false.",
    "remove_create": "A photo can only be removed from an existing gift.",
    "photo_conflict": "Choose a replacement photo or remove the photo, not both.",
    "photo_invalid": "Choose a valid, still JPEG or PNG photo.",
    "photo_large": "Choose a photo of 5 MiB or less and no more than 25 megapixels.",
}
UPLOAD_MESSAGE = "Couldn’t upload the photo. Nothing was saved. Try again or save without the photo."


def validation_message(error: ValidationError) -> str:
    return VALIDATION_MESSAGES.get(error.code, "Invalid gift data.")


def serialize_gift(gift: Gift, *, user_id: int) -> dict[str, object]:
    if gift.user_id != user_id:
        raise PermissionError("Gift does not belong to this user")
    return {
        "id": gift.id,
        "title": gift.title,
        "body": gift.body,
        "image_url": wishlist_storage.photo_url(gift.image_url),
        "timestamp": gift.timestamp.isoformat() if gift.timestamp else None,
        "user_id": gift.user_id,
    }


def clean_text(value, field: str, *, creating=False) -> str:
    if not isinstance(value, str):
        raise ValidationError("text_type")
    cleaned = value.strip()
    if not cleaned:
        if creating:
            raise ValidationError("required")
        raise EmptyTitleError() if field == "title" else EmptyBodyError()
    if len(cleaned) > 140:
        raise ValidationError("text_length")
    return cleaned


def parse_remove_image(value, *, multipart=False) -> bool:
    if type(value) is bool:
        return value
    if multipart and value in ("true", "false"):
        return value == "true"
    raise ValidationError("remove_flag")


def prepare_image(file_obj) -> tuple[io.BytesIO, str, str]:
    """Bound decoding, validate bytes, orient/resize, and discard all metadata."""
    data = file_obj.read(MAX_IMAGE_BYTES + 1)
    if len(data) > MAX_IMAGE_BYTES:
        raise ValidationError("photo_large")
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(data)) as probe:
                image_format = probe.format
                if image_format not in ("JPEG", "PNG") or getattr(probe, "n_frames", 1) != 1:
                    raise ValidationError("photo_invalid")
                if probe.width * probe.height > MAX_IMAGE_PIXELS:
                    raise ValidationError("photo_large")
                probe.verify()
            with Image.open(io.BytesIO(data)) as source:
                oriented = ImageOps.exif_transpose(source)
                oriented.thumbnail((2048, 2048))
                has_alpha = "A" in oriented.getbands() or "transparency" in oriented.info
                mode = "RGBA" if image_format == "PNG" and has_alpha else "RGB"
                converted = oriented.convert(mode)
                sanitized = Image.new(mode, converted.size)
                sanitized.paste(converted)
                output = io.BytesIO()
                options = {"quality": 85} if image_format == "JPEG" else {}
                sanitized.save(output, format=image_format, **options)
    except (Image.DecompressionBombError, Image.DecompressionBombWarning) as error:
        raise ValidationError("photo_large") from error
    except (UnidentifiedImageError, OSError, ValueError, SyntaxError) as error:
        raise ValidationError("photo_invalid") from error
    if output.tell() > MAX_IMAGE_BYTES:
        raise ValidationError("photo_large")
    output.seek(0)
    return output, "jpg" if image_format == "JPEG" else "png", "image/jpeg" if image_format == "JPEG" else "image/png"


def upload_image_to_s3(file_obj) -> str:
    """Use immutable keys; removal never deletes shared/legacy storage objects."""
    image, extension, content_type = prepare_image(file_obj)
    bucket_name = os.getenv("WISHLIST_S3_BUCKET")
    if not bucket_name:
        raise UploadError("Wishlist bucket is not configured")
    key = f"w/{uuid4().hex}.{extension}"
    url = f"https://{bucket_name}.s3.amazonaws.com/{key}"
    if len(url) > 140:
        raise UploadError("Wishlist image URL exceeds the storage column")
    try:
        s3 = wishlist_storage.s3_client()
        s3.upload_fileobj(image, bucket_name, key, ExtraArgs={
            "ContentType": content_type, "CacheControl": wishlist_storage.PHOTO_CACHE_CONTROL,
        })
    except (BotoCoreError, ClientError, S3UploadFailedError) as error:
        raise UploadError("Wishlist S3 upload failed") from error
    return url


def list_gifts_for_user(user_id: int) -> list[Gift]:
    return db.session.execute(db.select(Gift).filter_by(user_id=user_id)).scalars().all()


def get_gift_for_user(*, user_id: int, gift_id: int) -> Gift | None:
    gift = db.session.get(Gift, gift_id)
    if gift is None or gift.user_id != user_id:
        return None
    return gift


def create_gift_for_user(*, user: User, title: str, body: str, image_file=None) -> Gift:
    cleaned_title = clean_text(title, "title", creating=True)
    cleaned_body = clean_text(body, "body", creating=True)
    image_url = upload_image_to_s3(image_file) if image_file is not None else None
    gift = Gift(title=cleaned_title, body=cleaned_body, author=user, image_url=image_url)
    try:
        db.session.add(gift)
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise
    return gift


def update_gift(*, gift: Gift, title=UNSET, body=UNSET, image_file=None, remove_image=False) -> Gift:
    # Finish validation and upload before touching the persistent instance.
    cleaned_title = clean_text(title, "title") if title is not UNSET else gift.title
    cleaned_body = clean_text(body, "body") if body is not UNSET else gift.body
    remove_image = parse_remove_image(remove_image)
    if remove_image and image_file is not None:
        raise ValidationError("photo_conflict")
    image_url = upload_image_to_s3(image_file) if image_file is not None else None if remove_image else gift.image_url
    try:
        gift.title, gift.body, gift.image_url = cleaned_title, cleaned_body, image_url
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise
    return gift


def delete_gift(gift: Gift) -> None:
    try:
        db.session.delete(gift)
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise
