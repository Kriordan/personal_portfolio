#!/usr/bin/env python3
"""Explicit, sequential Browserless evaluation; never imports the app or uploads to S3.

Use a reviewed manifest of public listings. Each selected entry makes ONE provider
request, without retries, proxies, CAPTCHA solving, cookies, or persisted sessions.
Credentials are read from a mode-0600 file or BROWSERLESS_TOKEN, never arguments.
"""
import argparse
import hashlib
import io
import ipaddress
import json
import os
from pathlib import Path
import re
import signal
import socket
import stat
import time
from datetime import datetime, timezone
from urllib.parse import urlsplit
import warnings

import requests
from PIL import Image

ENDPOINT = "https://production-sfo.browserless.io/screenshot"
MAX_BYTES = 8 * 1024 * 1024
MAX_PIXELS = 24_000_000
DEADLINE_SECONDS = 22
ALLOWED_HOSTS = {
    "example.com", "job-boards.greenhouse.io", "jobs.lever.co",
    "jobs.eu.lever.co", "jobs.ashbyhq.com", "visa.wd5.myworkdayjobs.com",
    "genesys.wd1.myworkdayjobs.com", "jobs.smartrecruiters.com",
}


def expired(_signum, _frame):
    raise TimeoutError("evaluation deadline")


def validate_target(url, *, dns=False):
    parsed = urlsplit(url)
    if (parsed.scheme != "https" or parsed.hostname not in ALLOWED_HOSTS
            or parsed.username or parsed.password or parsed.port not in (None, 443)
            or parsed.query or parsed.fragment or len(url) > 2048
            or any(ord(c) < 32 for c in url)):
        raise ValueError("Only reviewed, query-free public HTTPS listings are allowed")
    if dns:
        addresses = socket.getaddrinfo(parsed.hostname, 443, type=socket.SOCK_STREAM)
        if not addresses or any(not ipaddress.ip_address(a[4][0]).is_global for a in addresses):
            raise ValueError("Target DNS is not public")


def load_token(path):
    if path:
        token_path = Path(path)
        if not stat.S_ISREG(token_path.stat().st_mode) or stat.S_IMODE(token_path.stat().st_mode) != 0o600:
            raise ValueError("Token file must be a regular file with mode 0600")
        token = token_path.read_text().strip()
    else:
        token = os.environ.get("BROWSERLESS_TOKEN", "").strip()
    if not token or token == "<redacted>" or any(c.isspace() for c in token):
        raise ValueError("A Browserless token is required; do not put it in command arguments")
    return token


def payload(url, recipe="initial"):
    body = {
        "url": url,
        "viewport": {"width": 1280, "height": 900, "deviceScaleFactor": 1},
        "gotoOptions": {"waitUntil": "domcontentloaded", "timeout": 10000},
        "waitForTimeout": 1000,
        "scrollPage": True,
        "bestAttempt": False,
        "options": {"type": "png", "fullPage": True},
    }
    if recipe in {"settled", "viewport-resize"}:
        body["waitForTimeout"] = 5000
        body["scrollPage"] = False
    if recipe == "viewport-resize":
        body["options"]["captureBeyondViewport"] = False
    return body


def capture(entry, token, output, recipe="initial"):
    started = time.monotonic()
    result = {"id": entry["id"], "url": entry["url"], "provider_request_started": False,
              "technical_result": "unknown", "visual_result": "not_reviewed"}
    signal.signal(signal.SIGALRM, expired)
    signal.setitimer(signal.ITIMER_REAL, DEADLINE_SECONDS)
    try:
        validate_target(entry["url"], dns=True)
        with requests.Session() as session:
            session.trust_env = False
            result["provider_request_started"] = True
            with session.post(ENDPOINT, params={"token": token, "timeout": 18000},
                    json=payload(entry["url"], recipe), headers={"Cache-Control": "no-store"},
                    stream=True, timeout=(2, 19), allow_redirects=False) as response:
                result["headers_seconds"] = round(time.monotonic() - started, 3)
                result["provider_status"] = response.status_code
                result["content_type"] = response.headers.get("Content-Type", "").split(";")[0].lower()
                # Deliberately omit URLs, arbitrary response bodies, and exception strings.
                for header, key in (("X-Response-Code", "target_status"),
                        ("X-Failed-Stylesheet-Count", "failed_stylesheets"),
                        ("X-Failed-Resource-Count", "failed_resources")):
                    value = response.headers.get(header, "")
                    result[key] = int(value) if value.isdecimal() else None
                if response.status_code != 200:
                    result["technical_result"] = "provider_http_error"
                    return result
                if result["content_type"] not in {"image/png", "image/jpeg"}:
                    result["technical_result"] = "unexpected_media_type"
                    return result
                data = bytearray()
                for chunk in response.iter_content(64 * 1024):
                    data.extend(chunk)
                    if len(data) > MAX_BYTES:
                        result["technical_result"] = "exceeds_8mib"
                        return result
                result["download_seconds"] = round(time.monotonic() - started, 3)
                result["download_bytes"] = len(data)
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(data)) as source:
                result["width"], result["height"] = source.size
                if source.format not in {"PNG", "JPEG"} or source.width * source.height > MAX_PIXELS:
                    result["technical_result"] = "image_exceeds_limits"
                    return result
                source.load()
                sanitized = Image.new("RGB", source.size)
                sanitized.paste(source.convert("RGB"))
                image = io.BytesIO()
                sanitized.save(image, format="PNG")
        if image.tell() > MAX_BYTES:
            result["technical_result"] = "sanitized_image_exceeds_8mib"
            return result
        image_bytes = image.getvalue()
        (output / (entry["id"] + ".png")).write_bytes(image_bytes)
        result["sha256"] = hashlib.sha256(image_bytes).hexdigest()
        result["stored_bytes"] = len(image_bytes)
        result["technical_result"] = "valid_image"
        if result.get("target_status") is not None and result["target_status"] >= 400:
            result["technical_result"] = "target_http_error_image"
    except (TimeoutError, requests.Timeout):
        result["technical_result"] = "timeout"
    except Exception as error:
        result["technical_result"] = "error"
        result["error_type"] = type(error).__name__  # Never print the exception message.
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        result["total_seconds"] = round(time.monotonic() - started, 3)
        result["within_18s_before_storage"] = result["total_seconds"] <= 18
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--token-file", type=Path)
    parser.add_argument("--ids", nargs="+")
    parser.add_argument("--recipe", choices=("initial", "settled", "viewport-resize"), default="initial")
    parser.add_argument("--run", action="store_true", help="Consume one request per selected listing")
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text())
    entries = manifest["listings"]
    if args.ids:
        if set(args.ids) - {entry["id"] for entry in entries}:
            parser.error("Unknown listing ID")
        entries = [entry for entry in entries if entry["id"] in args.ids]
    if not 1 <= len(entries) <= 15 or len({e["id"] for e in entries}) != len(entries):
        parser.error("Select 1–15 unique entries")
    for entry in entries:
        if not re.fullmatch(r"[a-z0-9-]{1,60}", entry["id"]):
            parser.error("Invalid listing ID")
        validate_target(entry["url"])
    if not args.run:
        print(json.dumps({"dry_run": True, "requests": len(entries),
                          "ids": [e["id"] for e in entries], "recipe": args.recipe,
                          "example_payload": payload(entries[0]["url"], args.recipe)}))
        return
    token = load_token(args.token_file)
    # A fresh directory is mandatory: accidental reruns never repeat paid requests.
    args.output.mkdir(parents=True, exist_ok=False, mode=0o700)
    report = {"started_at": datetime.now(timezone.utc).isoformat(), "endpoint": ENDPOINT,
              "recipe": args.recipe, "example_payload": payload(entries[0]["url"], args.recipe),
              "deadline_seconds": DEADLINE_SECONDS, "provider_timeout_ms": 18000,
              "storage_upload_tested": False, "actual_billed_units": None,
              "network_origin": "local Mac; not Heroku", "results": []}
    for entry in entries:
        result = capture(entry, token, args.output, args.recipe)
        report["results"].append(result)
        (args.output / "results.json").write_text(json.dumps(report, indent=2) + "\n")
        print(json.dumps(result), flush=True)
        if result.get("provider_status") in {400, 401, 402, 403, 429}:
            print("Stopped: configuration, account, or rate limit needs review.", flush=True)
            break


if __name__ == "__main__":
    main()
