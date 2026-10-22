"""Bounded child process: no DB access, no stdout except sanitized artifact metadata.

The parent kills and waits for this process at 22 seconds, including DNS, provider
streaming, image decoding and S3. No unattended thread/task outlives the request.
"""
import base64
import io
import ipaddress
import json
import os
import re
import socket
import signal
import sys
import warnings
from pathlib import Path
from urllib.parse import urlsplit

import boto3
import requests
from botocore.config import Config
from PIL import Image
from project.jobwizard.capture_policy import CaptureError, target_profile

MAX_BYTES = 8 * 1024 * 1024
MAX_PIXELS = 24_000_000
MAX_RESPONSE_BYTES = ((MAX_BYTES + 2) // 3) * 4 + 4096
PROVIDER_CODE = Path(__file__).with_name("browserless_capture.mjs").read_text()


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
    profile = target_profile(url)
    if not profile:
        raise CaptureError("unsupported_target")
    validate_public_target(url)
    storage = s3_client()
    block = storage.get_public_access_block(Bucket=bucket())["PublicAccessBlockConfiguration"]
    if not all(block.get(setting) is True for setting in (
        "BlockPublicAcls", "IgnorePublicAcls", "BlockPublicPolicy", "RestrictPublicBuckets")):
        raise ValueError("private storage required")
    data = browserless_image(url, profile)
    with warnings.catch_warnings():
        warnings.simplefilter("error", Image.DecompressionBombWarning)
        with Image.open(io.BytesIO(data)) as image:
            if image.format not in {"PNG", "JPEG"}:
                raise CaptureError()
            if image.width * image.height > MAX_PIXELS:
                raise CaptureError("image_too_large")
            width, height = image.size
            image.load()
            output = io.BytesIO()
            sanitized = Image.new("RGB", image.size)
            sanitized.paste(image.convert("RGB"))
            sanitized.save(output, format="PNG")
    if output.tell() > MAX_BYTES:
        raise CaptureError("image_too_large")
    storage.put_object(Bucket=bucket(), Key=key, Body=output.getvalue(), ContentType="image/png", CacheControl="private, no-store")
    return {"object_key": key, "width": width, "height": height}


def browserless_image(url, profile):
    """One bounded, non-retried request. Never expose the token-bearing URL."""
    with requests.Session() as session:
        session.trust_env = False
        try:
            with session.post("https://production-sfo.browserless.io/function", params={
                "token": os.environ["BROWSERLESS_API_TOKEN"], "timeout": 16000,
            }, json={"code": PROVIDER_CODE, "context": {"url": url, "profile": profile}},
                    stream=True, timeout=(2, 17), allow_redirects=False) as response:
                code = {401: "provider_auth", 403: "provider_access", 402: "provider_quota",
                        429: "provider_busy", 408: "capture_timeout", 504: "capture_timeout"}.get(response.status_code)
                if code:
                    raise CaptureError(code)
                if response.status_code != 200 or response.headers.get("Content-Type", "").split(";")[0].lower() != "application/json":
                    raise CaptureError()
                raw = bytearray()
                for chunk in response.iter_content(64 * 1024):
                    raw.extend(chunk)
                    if len(raw) > MAX_RESPONSE_BYTES:
                        raise CaptureError("image_too_large")
        except requests.Timeout:
            raise CaptureError("capture_timeout") from None
    payload = json.loads(raw)
    if not isinstance(payload, dict) or payload.get("type") != "application/json" or not isinstance(payload.get("data"), dict):
        raise CaptureError()
    result = payload["data"]
    if "error" in result:
        raise CaptureError(result["error"] if isinstance(result["error"], str) else "capture_failed")
    data = base64.b64decode(result["image"], validate=True)
    if len(data) > MAX_BYTES:
        raise CaptureError("image_too_large")
    return data


def guard_worker(parent_pid):
    """Bound orphan lifetime too; Linux production dies with its web process."""
    if type(parent_pid) is not int or parent_pid != os.getppid():
        raise RuntimeError("parent unavailable")
    signal.signal(signal.SIGALRM, signal.SIG_DFL)
    signal.alarm(21)
    if sys.platform == "linux":
        import ctypes
        # Configure in the fresh child, never preexec_fn in a threaded server.
        libc = ctypes.CDLL(None, use_errno=True)
        if libc.prctl(1, signal.SIGKILL, 0, 0, 0) != 0:
            raise RuntimeError("parent monitoring unavailable")
        if parent_pid != os.getppid():
            raise RuntimeError("parent unavailable")


def main():
    try:
        # JSON escaping can expand a valid 2,048-character URL to over 8 KiB.
        payload = json.loads(sys.stdin.read(16384))
        guard_worker(payload["parent_pid"])
        result = capture_artifact(payload["url"], payload["key"])
        print(json.dumps(result))
    except Exception as error:
        # Exceptions can include the provider API key, signed links or listing URL.
        print(json.dumps({"error": error.code if isinstance(error, CaptureError) else "capture_failed"}))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
