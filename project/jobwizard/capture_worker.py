"""Bounded child process: no DB access, no stdout except sanitized artifact metadata.

The parent kills and waits for this process at 22 seconds, including DNS, provider
streaming, image decoding and S3. No unattended thread/task outlives the request.
"""
import io
import ipaddress
import json
import os
import re
import socket
import sys
import warnings
from urllib.parse import urlsplit

import boto3
import requests
from botocore.config import Config
from PIL import Image

MAX_BYTES = 8 * 1024 * 1024
MAX_PIXELS = 24_000_000


def bucket():
    return os.getenv("JOBWIZARD_PRIVATE_S3_BUCKET", "")


def region():
    return os.getenv("JOBWIZARD_S3_REGION") or os.getenv("AWS_DEFAULT_REGION") or "us-east-1"


def s3_client():
    return boto3.client("s3", region_name=region(), config=Config(
        signature_version="s3v4", connect_timeout=2, read_timeout=4,
        retries={"total_max_attempts": 1}, s3={"addressing_style": "virtual"}))


def validate_public_target(url):
    from project.services.jobwizard_service import safe_listing_url
    if not safe_listing_url(url):
        raise ValueError("invalid target")
    parsed = urlsplit(url)
    host = parsed.hostname.rstrip(".").lower()
    if "." not in host or host.endswith((".localhost", ".local", ".internal", ".test")):
        raise ValueError("invalid target")
    addresses = socket.getaddrinfo(host, parsed.port or (443 if parsed.scheme == "https" else 80), type=socket.SOCK_STREAM)
    if not addresses or any(not ipaddress.ip_address(address[4][0]).is_global for address in addresses):
        raise ValueError("nonpublic target")


def capture_artifact(url, key):
    if not re.fullmatch(r"j/[a-f0-9]{32}\.png", key):
        raise ValueError("invalid key")
    validate_public_target(url)
    storage = s3_client()
    block = storage.get_public_access_block(Bucket=bucket())["PublicAccessBlockConfiguration"]
    if not all(block.get(setting) is True for setting in (
        "BlockPublicAcls", "IgnorePublicAcls", "BlockPublicPolicy", "RestrictPublicBuckets")):
        raise ValueError("private storage required")
    with requests.get("https://apileap.com/api/screenshot/v1/urltoimage", params={
        "url": url, "access_key": os.environ["APILEAP_ACCESS_KEY"], "full_page": "true",
    }, stream=True, timeout=(2, 12), allow_redirects=False) as response:
        if response.status_code != 200 or response.headers.get("Content-Type", "").split(";")[0].lower() not in {"image/png", "image/jpeg"}:
            raise ValueError("invalid provider response")
        data = bytearray()
        for chunk in response.iter_content(64 * 1024):
            data.extend(chunk)
            if len(data) > MAX_BYTES:
                raise ValueError("image too large")
    with warnings.catch_warnings():
        warnings.simplefilter("error", Image.DecompressionBombWarning)
        with Image.open(io.BytesIO(data)) as image:
            if image.format not in {"PNG", "JPEG"} or image.width * image.height > MAX_PIXELS:
                raise ValueError("invalid image")
            width, height = image.size
            image.load()
            output = io.BytesIO()
            image.convert("RGB").save(output, format="PNG")
    if output.tell() > MAX_BYTES:
        raise ValueError("image too large")
    storage.put_object(Bucket=bucket(), Key=key, Body=output.getvalue(), ContentType="image/png", CacheControl="private, no-store")
    return {"object_key": key, "width": width, "height": height}


def main():
    try:
        payload = json.loads(sys.stdin.read(8192))
        result = capture_artifact(payload["url"], payload["key"])
        print(json.dumps(result))
    except Exception:
        # Exceptions can include the provider API key, signed links or listing URL.
        print('{"error":"capture_failed"}')
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
