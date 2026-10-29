"""One Learning call to the OpenAI Responses API, in a short-lived child process.

`project/services/learning_ai_provider.py` runs this as `python -I learning_ai_call.py` with a
minimal environment, so it imports only the standard library and requests. It reads one JSON
request on stdin and prints one JSON line: the model's JSON object and usage, or a fixed error
code and whether the provider may have charged ("no", "yes", or "unknown"). Exception text is
never printed: it can contain the key. At the deadline SIGALRM's default action ends the process.
"""
import json
import math
import os
import re
import signal
import sys
import time
from urllib.parse import urlsplit

import requests

# The request arrives as UTF-8 JSON: well over twice a large context allowance (the reply's input is
# JSON inside JSON, so its escapes double), with room to spare.
MAX_INPUT_BYTES = 8 * 1024 * 1024
# Statuses where the provider refused before doing paid work ("no"), or may have done it.
STATUS_ERRORS = {400: ("provider_request", "no"), 404: ("provider_request", "no"),
                 401: ("provider_auth", "no"), 403: ("provider_auth", "no"),
                 402: ("provider_quota", "no"), 429: ("provider_quota", "no"),
                 408: ("timeout", "unknown"), 504: ("timeout", "unknown")}


class CallError(Exception):
    """A failure with a fixed code, and whether the provider may have charged for it."""

    def __init__(self, code, charged):
        super().__init__(code)
        self.code, self.charged = code, charged


def guard(parent_pid):
    """Refuse an orphaned start and, on Linux, die with the parent (JobWizard's guard_worker, copied)."""
    if type(parent_pid) is not int or parent_pid != os.getppid():
        raise CallError("failed", "no")
    signal.signal(signal.SIGALRM, signal.SIG_DFL)
    if sys.platform == "linux":
        import ctypes
        # Configure in the fresh child, never preexec_fn in a threaded server.
        libc = ctypes.CDLL(None, use_errno=True)
        if libc.prctl(1, signal.SIGKILL, 0, 0, 0) != 0:  # PR_SET_PDEATHSIG
            raise CallError("failed", "no")
        if parent_pid != os.getppid():
            raise CallError("failed", "no")


def allowed_base(url):
    """HTTPS, or plain HTTP to a local test server; never credentials, a query, or a fragment."""
    if not isinstance(url, str) or not re.fullmatch(r"[A-Za-z0-9.:/_~-]+", url):
        return False
    parts = urlsplit(url)
    port = parts.port  # An invalid port raises here, before any request.
    if parts.scheme == "http":
        return parts.hostname in ("127.0.0.1", "localhost") and bool(port)
    return parts.scheme == "https" and bool(parts.hostname)


def read_json(response, limit):
    """The response's JSON object, read in chunks of at most `limit` bytes in all."""
    status = response.status_code
    if status != 200:
        raise CallError(*STATUS_ERRORS.get(status, ("provider" if 500 <= status < 600 else "failed", "unknown")))
    if response.headers.get("Content-Type", "").split(";")[0].strip().lower() != "application/json":
        raise CallError("provider", "unknown")
    raw = bytearray()
    for part in response.iter_content(65536):
        raw.extend(part)
        if len(raw) > limit:
            raise CallError("too_large", "unknown")
    try:
        data = json.loads(raw)
    except ValueError:
        data = None
    if not isinstance(data, dict):
        raise CallError("provider", "unknown")
    return data


def _dict(value):
    return value if isinstance(value, dict) else {}


def _list(value):
    return value if isinstance(value, list) else []


def usage_of(data):
    """Token counts in the ledger's terms, or None when they can't be trusted."""
    usage = _dict(data.get("usage"))
    tokens = {"input_tokens": usage.get("input_tokens"), "output_tokens": usage.get("output_tokens"),
              "cached_input_tokens": _dict(usage.get("input_tokens_details")).get("cached_tokens", 0)}
    trusted = all(type(value) is int and value >= 0 for value in tokens.values())
    return tokens if trusted and tokens["cached_input_tokens"] <= tokens["input_tokens"] else None


def output_of(data):
    """The model's output as a JSON object; anything else raises a CallError."""
    content = [part for item in _list(data.get("output")) if _dict(item).get("type") == "message"
               for part in _list(item.get("content")) if isinstance(part, dict)]
    if any(part.get("type") == "refusal" for part in content):
        raise CallError("refused", "yes")
    if data.get("status") == "incomplete":
        raise CallError("incomplete", "yes")
    if data.get("status") != "completed":
        raise CallError("provider", "unknown")
    try:
        value = json.loads("".join(part.get("text", "") for part in content if part.get("type") == "output_text"))
    except (TypeError, ValueError):
        value = None
    if not isinstance(value, dict):
        raise CallError("invalid_output", "yes")
    return value


def failure(error, *, sent):
    """An exception's fixed code, and whether the call may have been charged. Never its text."""
    if isinstance(error, CallError):
        return error.code, error.charged
    if not sent:
        return "failed", "no"
    if isinstance(error, requests.exceptions.ConnectTimeout):
        return "timeout", "no"  # Never connected, so nothing was sent.
    if isinstance(error, requests.Timeout):
        return "timeout", "unknown"
    if isinstance(error, requests.RequestException):
        return "provider", "unknown"
    return "failed", "unknown"


def main():
    usage = started = None
    try:
        raw = sys.stdin.buffer.read(MAX_INPUT_BYTES + 1)
        if len(raw) > MAX_INPUT_BYTES:
            raise CallError("failed", "no")
        payload = json.loads(raw)
        base_url, body = payload["base_url"], payload["body"]
        deadline, limit = payload["deadline"], payload["max_response_bytes"]
        if (not allowed_base(base_url) or not isinstance(body, dict) or type(deadline) not in (int, float)
                or not 0 < deadline < math.inf or type(limit) is not int or limit <= 0):
            raise CallError("failed", "no")
        key = os.environ.get("LEARNING_OPENAI_API_KEY")
        if not key:
            raise CallError("provider_auth", "no")
        guard(payload["parent_pid"])
        signal.alarm(math.ceil(deadline))
        started = time.monotonic()
        try:
            with requests.Session() as session:
                session.trust_env = False
                with session.post(base_url.rstrip("/") + "/responses", headers={"Authorization": "Bearer " + key},
                                  json=body, stream=True, timeout=(5, deadline), allow_redirects=False,
                                  verify=os.environ.get("REQUESTS_CA_BUNDLE") or True) as response:
                    data = read_json(response, limit)
        finally:
            signal.alarm(0)  # The call is over: a late alarm mustn't turn its outcome into a timeout.
        usage = usage_of(data)
        result, status = {"output": output_of(data), "usage": usage}, 0
    except Exception as error:
        code, charged = failure(error, sent=started is not None)
        result, status = {"error": code, "charged": charged, "usage": usage}, 1
    result["seconds"] = 0.0 if started is None else round(time.monotonic() - started, 3)
    print(json.dumps(result))
    return status


if __name__ == "__main__":
    sys.exit(main())
