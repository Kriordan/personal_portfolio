"""Bounded, disposable provider process. No jobs, notes, images or DB operations."""
import json
import os
from pathlib import Path
import signal
import sys
import time

import requests

from project.jobwizard.capture_policy import target_profile
from project.jobwizard.capture_worker import guard_worker, validate_public_target
from project.jobwizard.extraction import normalize_source, summary_request, validate_summary, ExtractionError
from project.jobwizard.extraction_errors import SuggestionError


def read_json(response, limit):
    if response.status_code != 200:
        raise SuggestionError({401: "provider_auth", 403: "provider_auth", 402: "provider_quota",
                               429: "provider_quota", 408: "timeout", 504: "timeout"}.get(response.status_code, "failed"))
    if response.headers.get("Content-Type", "").split(";")[0].lower() != "application/json":
        raise SuggestionError()
    raw = bytearray()
    for part in response.iter_content(65536):
        raw.extend(part)
        if len(raw) > limit:
            raise SuggestionError("too_large")
    return json.loads(raw)


def read_listing(url):
    profile = target_profile(url)
    if not profile:
        raise SuggestionError("unsupported")
    validate_public_target(url)
    folder = Path(__file__).parent
    common = (folder / "browserless_capture.mjs").read_text()
    extract = (folder / "browserless_extract.mjs").read_text()
    code = common.replace("export default async function capture", "async function capture") + "\n" + "\n".join(extract.splitlines()[1:])
    with requests.Session() as client:
        client.trust_env = False
        with client.post("https://production-sfo.browserless.io/function",
                params={"token": os.environ["BROWSERLESS_API_TOKEN"], "timeout": 16000},
                json={"code": code, "context": {"url": url, "profile": profile}},
                stream=True, timeout=(2, 16), allow_redirects=False) as response:
            payload = read_json(response, 1_000_000)
    if not isinstance(payload, dict) or not isinstance(payload.get("data"), dict):
        raise SuggestionError()
    raw = payload["data"]
    if raw.get("error"):
        raise SuggestionError(raw["error"])
    return {"source": normalize_source(raw, url, profile)}


def summarize(source, model):
    with requests.Session() as client:
        client.trust_env = False
        with client.post("https://api.openai.com/v1/responses",
                headers={"Authorization": "Bearer " + os.environ["OPENAI_API_KEY"]},
                json=summary_request(source, model), stream=True, timeout=(2, 9), allow_redirects=False) as response:
            data = read_json(response, 250_000)
    content = [part for item in data.get("output", []) if item.get("type") == "message" for part in item.get("content", [])]
    if any(part.get("type") == "refusal" for part in content):
        raise SuggestionError("refused")
    if data.get("status") != "completed":
        raise SuggestionError("invalid_summary")
    try:
        value = json.loads("".join(part.get("text", "") for part in content if part.get("type") == "output_text"))
        result = validate_summary(value, source)
    except (ValueError, TypeError, KeyError):
        raise SuggestionError("invalid_summary") from None
    usage = data.get("usage") or {}
    return {"result": result, "usage": {key: usage[key] for key in ("input_tokens", "output_tokens", "total_tokens")
                                       if type(usage.get(key)) is int and usage[key] >= 0}, "model": model}


def main():
    try:
        payload = json.loads(sys.stdin.read(1_000_000))
        guard_worker(payload["parent_pid"])
        signal.alarm(18 if payload["stage"] == "read" else 10)
        started = time.monotonic()
        result = read_listing(payload["url"]) if payload["stage"] == "read" else summarize(payload["source"], payload["model"])
        result["seconds"] = round(time.monotonic() - started, 3)
        print(json.dumps(result))
        return 0
    except Exception as error:
        code = error.code if isinstance(error, SuggestionError) else "timeout" if isinstance(error, requests.Timeout) else "failed"
        if isinstance(error, ExtractionError):
            code = "too_large" if "large" in str(error) else "page_unavailable"
        print(json.dumps({"error": code}))
        return 1


if __name__ == "__main__":
    sys.exit(main())
