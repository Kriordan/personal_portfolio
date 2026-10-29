"""The Learning interviewer's OpenAI provider: each call runs in a short-lived child process.

The child, `project/learning_ai_call.py`, runs with `python -I` and an environment holding only
the key, PATH, and CA bundle settings. Its own alarm and the timeout here bound it, so a stuck
call can always be abandoned. Its stderr is discarded: failures arrive as fixed codes, with
whether the provider may have charged for the call, never as provider or exception text.
"""
import json
import os
import subprocess
import sys
import time
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "learning_ai_call.py"
KEY_VARIABLE = "LEARNING_OPENAI_API_KEY"
# Passed on when set, so TLS verification honours a custom trust store.
CA_VARIABLES = ("SSL_CERT_FILE", "SSL_CERT_DIR", "REQUESTS_CA_BUNDLE")
CODES = ("provider", "provider_auth", "provider_quota", "provider_request", "timeout", "too_large",
         "refused", "incomplete", "invalid_output", "failed")
CHARGED = ("no", "yes", "unknown")
USAGE_KEYS = ("input_tokens", "cached_input_tokens", "output_tokens")


class ProviderError(Exception):
    """A provider call that produced no usable reply.

    `charged` says what the ledger records: "no" releases the reservation, "yes" settles it
    (from `usage` when known), and "unknown" leaves it reserved as an uncertain cost.
    """

    def __init__(self, code, *, charged="unknown", usage=None):
        super().__init__(code)
        self.code, self.charged, self.usage = code, charged, usage


def child_environment(environ=None):
    """The child's entire environment: the key, PATH, and the CA bundle settings that are set."""
    environ = os.environ if environ is None else environ
    return {name: environ[name] for name in (KEY_VARIABLE, "PATH", *CA_VARIABLES) if environ.get(name)}


def _usage(value):
    """Usage in the ledger's terms, or None when it isn't well formed."""
    if not isinstance(value, dict) or not all(type(value.get(key)) is int and value[key] >= 0 for key in USAGE_KEYS):
        return None
    return {key: value[key] for key in USAGE_KEYS} if value["cached_input_tokens"] <= value["input_tokens"] else None


class OpenAIProvider:
    """Calls the OpenAI Responses API. `base_url` may name a local test server instead."""

    def __init__(self, *, base_url="https://api.openai.com/v1", max_response_bytes=1_048_576, python=sys.executable):
        self.base_url, self.max_response_bytes, self.python = base_url, max_response_bytes, python

    def call(self, body, *, deadline):
        """Make one call within `deadline` seconds. Returns {"output", "usage", "seconds", "spawn_seconds"}.

        `seconds` is the request's time in the child and `spawn_seconds` the rest of the wall
        time (starting Python, imports, and exit). Raises ProviderError when there's no output.
        """
        if not os.environ.get(KEY_VARIABLE):
            raise ProviderError("provider_auth", charged="no")
        payload = {"parent_pid": os.getpid(), "deadline": deadline, "base_url": self.base_url,
                   "body": body, "max_response_bytes": self.max_response_bytes}
        started = time.monotonic()
        try:
            result = subprocess.run([self.python, "-I", str(SCRIPT)], input=json.dumps(payload, ensure_ascii=False),
                                    stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, encoding="utf-8",
                                    timeout=deadline + 5, env=child_environment(), cwd=SCRIPT.parent)
        except subprocess.TimeoutExpired:
            raise ProviderError("timeout", charged="unknown") from None
        except OSError:  # Usually the child couldn't start, but stay conservative.
            raise ProviderError("failed", charged="unknown") from None
        wall = time.monotonic() - started
        if result.returncode < 0:
            # Killed: usually the child's own alarm at the deadline (SIGALRM, -14).
            raise ProviderError("timeout", charged="unknown")
        try:
            data = json.loads(result.stdout)
        except ValueError:
            data = None
        if not isinstance(data, dict):
            raise ProviderError("failed", charged="unknown")
        if result.returncode == 0 and "error" not in data and isinstance(data.get("output"), dict):
            seconds = data.get("seconds")
            seconds = float(seconds) if type(seconds) in (int, float) and seconds >= 0 else 0.0
            return {"output": data["output"], "usage": _usage(data.get("usage")), "seconds": seconds,
                    "spawn_seconds": round(max(wall - seconds, 0.0), 3)}
        code, charged = data.get("error"), data.get("charged")
        raise ProviderError(code if code in CODES else "failed", charged=charged if charged in CHARGED else "unknown",
                            usage=_usage(data.get("usage")))
