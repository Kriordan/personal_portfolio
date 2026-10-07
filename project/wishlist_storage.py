"""Private Wishlist photo delivery; stored references never contain credentials."""

import logging
import os
import re
from urllib.parse import urlsplit

import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError

PHOTO_URL_TTL_SECONDS = 15 * 60
PHOTO_CACHE_CONTROL = "private, no-store"
logger = logging.getLogger(__name__)


def bucket_name():
    return os.getenv("WISHLIST_S3_BUCKET")


def bucket_region():
    return os.getenv("WISHLIST_S3_REGION") or os.getenv("AWS_DEFAULT_REGION") or "us-east-1"


def image_origins():
    bucket = bucket_name()
    if not bucket:
        return []
    region = bucket_region()
    return [
        f"https://{bucket}.s3.amazonaws.com",
        f"https://{bucket}.s3.{region}.amazonaws.com",
        f"https://{bucket}.s3-{region}.amazonaws.com",
    ]


def s3_client():
    return boto3.client(
        "s3", region_name=bucket_region(),
        config=Config(
            signature_version="s3v4", s3={"addressing_style": "virtual"},
            connect_timeout=5, read_timeout=20, retries={"total_max_attempts": 1},
        ),
    )


def photo_url(stored_url):
    """Called only after gift ownership is checked by serialize_gift.

    Sign only our immutable w/<uuid> keys in the configured bucket. Older
    external references keep their existing access behavior; never sign them.
    """
    if not stored_url:
        return stored_url
    try:
        parsed = urlsplit(stored_url)
    except ValueError:
        return stored_url
    origin = f"{parsed.scheme}://{parsed.netloc}"
    if (origin not in image_origins() or parsed.query or parsed.fragment
            or not re.fullmatch(r"/w/[a-f0-9]{32}\.(?:jpg|png)", parsed.path)):
        return stored_url
    try:
        return s3_client().generate_presigned_url(
            "get_object",
            Params={
                "Bucket": bucket_name(), "Key": parsed.path[1:],
                "ResponseCacheControl": PHOTO_CACHE_CONTROL,
            },
            ExpiresIn=PHOTO_URL_TTL_SECONDS,
        )
    except (BotoCoreError, ClientError):
        # A read/signing failure must not report a committed save as failed.
        # The private, unsigned reference produces the client's photo fallback
        # and still lets the owner remove or replace the unavailable photo.
        logger.warning("Wishlist photo signing unavailable")
        return stored_url
