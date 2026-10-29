"""The Learning reply worker: one tracked thread in the web process, or a process of its own.

Replies are database rows with leases, so a restart loses nothing: a stale reply reads as
interrupted and the learner asks again. Paid calls are never retried automatically. Each
provider call goes through an injectable provider: the scripted FakeProvider here, or
OpenAIProvider (learning_ai_provider), which makes each call in a short-lived child process
so a stuck call can always be abandoned. A reply is up to two calls: the selector, then the
reply. Logs and error reports carry fixed codes only, never learner text or model output.
"""
from __future__ import annotations

import json
import os
import re
import socket
import threading
import time
from datetime import datetime, timezone

import click
from flask import current_app
from flask.cli import with_appcontext
from sqlalchemy.exc import OperationalError

from project import monitoring
from project.database import db
from project.learning import interviewer
from project.services import practice_budget, practice_service, practice_signals
from project.services.learning_ai_provider import OpenAIProvider, ProviderError

FAKE_MODES = ("success", "slow", "fail", "lost", "hang", "invalid")
# Expected outcomes that are logged but not reported as errors.
QUIET_CODES = {"budget", "unpriced", "context_too_large"}
# Words too common to show what a message asks about, for the fake selector.
_COMMON = {"about", "after", "also", "been", "before", "could", "does", "each", "from", "have", "happen", "happens",
           "into", "just", "like", "more", "must", "need", "only", "other", "same", "should", "some", "than", "that",
           "their", "them", "then", "there", "they", "this", "what", "when", "where", "which", "while", "will",
           "with", "would", "your"}


def _words(text):
    words = set()
    for word in re.findall(r"[a-z0-9]+", text.lower()):
        word = word[:-1] if word.endswith("s") and len(word) > 4 else word
        if len(word) >= 4 and word not in _COMMON:
            words.add(word)
    return words


def fake_selection(body):
    """A deterministic stand-in for the selector: a requirement whose cue the message repeats, or
    shares two distinctive words with, and a hint when the message asks for one. Real paraphrase
    detection is the live model's job, measured by the evaluation harness."""
    material = json.loads(body["input"])
    message = material["message"]
    said = _words(message)
    chosen = [requirement["id"] for requirement in material["requirements"]
              if any(cue.lower().strip(" ?") in message.lower() or len(_words(cue) & said) >= 2
                     for cue in requirement["cues"])]
    properties = body["text"]["format"]["schema"]["properties"]
    output = {}
    if "constraint_ids" in properties:
        output["constraint_ids"] = chosen
    if "hint_requested" in properties:
        output["hint_requested"] = bool(re.search(r"\bhint\b|\bhelp me\b", message, re.I))
    return output


class FakeProvider:
    """Scripted answers for tests, the preview fixture, and the evaluation harness. It never
    contacts a network.

    `mode` may be a callable, so a running fixture can switch it: success, slow, fail
    (refused before any paid work), lost (outcome unknown), hang (until the deadline), or
    invalid (an empty reply). Selector calls answer from `selections` when scripted (each a
    dict, or a callable given the request), else from `fake_selection`; reply calls from
    `replies`, else a fixed question.
    """

    def __init__(self, mode="success", *, delay=2.0, replies=(), selections=()):
        self.mode, self.delay, self.replies, self.selections = mode, delay, list(replies), list(selections)
        self.calls = []

    def call(self, body, *, deadline):
        self.calls.append(body)
        mode = self.mode() if callable(self.mode) else self.mode
        if mode == "fail":
            raise ProviderError("provider", charged="no")
        if mode == "lost":
            raise ProviderError("timeout")
        if mode == "hang":
            time.sleep(deadline)
            raise ProviderError("timeout")
        if mode == "slow":
            time.sleep(self.delay)
        if body["text"]["format"]["name"] == interviewer.SELECTOR_SCHEMA_NAME:
            scripted = self.selections.pop(0) if self.selections else fake_selection
            output = scripted(body) if callable(scripted) else scripted
            text = json.dumps(output)
        else:
            text = "" if mode == "invalid" else (
                self.replies.pop(0) if self.replies else "What should happen when the same order request arrives twice?")
            output = {"reply": text}
        size = len(json.dumps(body, ensure_ascii=False).encode("utf-8"))
        return {"output": output,
                "usage": {"input_tokens": size // 4, "cached_input_tokens": 0, "output_tokens": max(len(text) // 4, 1)}}

    def reply_calls(self):
        return [body for body in self.calls if body["text"]["format"]["name"] == interviewer.REPLY_SCHEMA_NAME]

    def selector_calls(self):
        return [body for body in self.calls if body["text"]["format"]["name"] == interviewer.SELECTOR_SCHEMA_NAME]


def provider_for(app):
    """The configured provider, or None when this release can't call it (OpenAI without its key)."""
    name = app.config.get("LEARNING_AI_PROVIDER", "openai")
    if name == "fake":
        return FakeProvider(app.config.get("LEARNING_AI_FAKE_MODE", "success"))
    if name == "openai" and os.environ.get("LEARNING_OPENAI_API_KEY"):
        return OpenAIProvider(base_url=app.config.get("LEARNING_AI_BASE_URL", "https://api.openai.com/v1"))
    return None


def _now():
    return datetime.now(timezone.utc)


def _report(code, reply_id=None):
    current_app.logger.warning("Learning reply not completed: %s", code)
    if code not in QUIET_CODES:
        monitoring.report_learning_failure(code, reply_id=reply_id)


def run_once(provider, *, now=_now, worker_id="worker"):
    """Sweep, then claim and run one pending reply. Returns whether a reply was claimed."""
    practice_service.sweep_replies(now())
    claimed = practice_service.claim_reply(now(), known_profiles=interviewer.PROFILES, worker_id=worker_id)
    if claimed is None:
        return False
    reply_id, token = claimed
    try:
        _run(provider, reply_id, token, now)
    except Exception as exc:
        db.session.rollback()
        current_app.logger.warning("Learning reply worker error: %s", practice_service.describe_failure(exc))
        monitoring.report_learning_failure("worker", reply_id=reply_id)
        try:
            practice_service.fail_reply(reply_id, token, code="failed", now=now())
        except Exception:
            db.session.rollback()
    return True


def _run(provider, reply_id, token, now):
    """One reply: the selector (when anything is left to reveal or hint), then the reply.

    If the selector fails, so does the reply: answering without it could withhold a fact the
    learner earned. Its cost is settled, nothing is revealed, and asking again reruns both.
    """
    context = practice_service.reply_context(reply_id)
    if context is None:
        return
    settings = practice_service.ai_settings()
    selection = {"constraint_ids": [], "hint_requested": False}
    selector = interviewer.selector_request(context, settings)
    if selector is not None:
        output = _call(provider, reply_id, token, selector, purpose="select", settings=settings, now=now)
        if output is None:
            return
        try:
            selection = interviewer.parse_selection(output, context)
        except interviewer.InvalidOutput:
            practice_service.fail_reply(reply_id, token, code="invalid_output", now=now())
            _report("invalid_output", reply_id)
            return
    facilitator = practice_service.reply_facilitator(context, selection)
    if facilitator is None:
        return
    body = interviewer.reply_request(context, facilitator, settings)
    if interviewer.prompt_bytes(body) > settings["context_bytes"]:
        practice_service.fail_reply(reply_id, token, code="context_too_large", now=now())
        _report("context_too_large", reply_id)
        return
    output = _call(provider, reply_id, token, body, purpose="reply", settings=settings, now=now)
    if output is None:
        return
    _complete(reply_id, token, output.get("reply"), now,
              disclosure={"constraint_ids": facilitator["constraint_ids"], "hint_index": facilitator["hint_index"]})


def _call(provider, reply_id, token, body, *, purpose, settings, now):
    """One paid call, fenced and reserved first and settled after. Returns its output object
    (empty when the provider's answer isn't one), or None when the reply stops here."""
    try:
        charge = practice_service.begin_call(reply_id, token, purpose=purpose, input_bytes=interviewer.body_bytes(body),
                                             max_output_tokens=body["max_output_tokens"],
                                             deadline_seconds=settings["call_seconds"], now=now())
    except practice_service.CallFenced:
        return None
    except practice_budget.BudgetExhausted as exc:
        _report(exc.code, reply_id)
        return None
    try:
        result = provider.call(body, deadline=settings["call_seconds"])
    except ProviderError as error:
        outcome = {"no": "released", "yes": "settled"}.get(error.charged, "uncertain")
        practice_service.finish_call(charge, outcome=outcome, usage=error.usage, now=now())
        practice_service.fail_reply(reply_id, token, code=error.code, now=now())
        _report(error.code, reply_id)
        return None
    practice_service.finish_call(charge, outcome="settled", usage=result.get("usage"), now=now())
    output = result.get("output")
    return output if isinstance(output, dict) else {}


def _complete(reply_id, token, reply, now, *, disclosure=None):
    """Write the reply, retrying the database write (never the paid call) on transient errors."""
    for attempt in range(3):
        try:
            if practice_service.complete_reply(reply_id, token, body=reply, now=now(),
                                               disclosure=disclosure) == "invalid":
                _report("invalid_output", reply_id)
            return
        except OperationalError:
            db.session.rollback()
            time.sleep(0.5 * (attempt + 1))
    # The reply was paid for but couldn't be stored; its lease expires and it reads as interrupted.
    _report("store", reply_id)


class Worker:
    """Runs replies one at a time, on a daemon thread or in the foreground."""

    def __init__(self, app, provider, *, poll_seconds=5.0):
        self.app, self.provider, self.poll_seconds = app, provider, poll_seconds
        self.worker_id = f"{socket.gethostname()}:{os.getpid()}"
        self._stop = threading.Event()
        # Guards _running, which says a thread will check _stop again before it exits.
        self._lock = threading.Lock()
        self._running = False
        self._thread = None

    def start(self):
        """Start the thread. A thread still finishing a call after stop() carries on instead of gaining a twin."""
        with self._lock:
            self._stop.clear()
            if not self._running:
                self._running = True
                self._thread = threading.Thread(target=self.run_forever, name="learning-ai-worker", daemon=True)
                self._thread.start()
        return self

    def stop(self, timeout=10):
        """Stop after the current reply. Returns whether the thread has ended."""
        self._stop.set()
        practice_signals.reply_queued.set()
        if self._thread is not None:
            self._thread.join(timeout)
        return self._thread is None or not self._thread.is_alive()

    def _exiting(self):
        with self._lock:
            if self._stop.is_set():
                self._running = False
                return True
            return False

    def run_forever(self):
        while not self._exiting():
            worked = False
            with self.app.app_context():
                try:
                    worked = run_once(self.provider, worker_id=self.worker_id)
                except Exception as exc:
                    db.session.rollback()
                    current_app.logger.warning("Learning reply worker error: %s",
                                               practice_service.describe_failure(exc))
                finally:
                    db.session.remove()
            if not worked and not self._stop.is_set():
                practice_signals.reply_queued.wait(self.poll_seconds)
                practice_signals.reply_queued.clear()


_worker = None
_worker_lock = threading.Lock()


def should_start(app):
    """Only the web entry point starts the thread, and only once under the debug reloader."""
    return (bool(app.config.get("LEARNING_AI_ENABLED")) and provider_for(app) is not None
            and (not app.debug or os.environ.get("WERKZEUG_RUN_MAIN") == "true"))


def start(app, provider=None, *, poll_seconds=5.0):
    """Start this process's worker thread once; later calls return the same worker."""
    global _worker
    with _worker_lock:
        if _worker is None:
            _worker = Worker(app, provider or provider_for(app), poll_seconds=poll_seconds)
        return _worker.start()


def stop(timeout=10):
    """Stop this process's worker thread. One still in a call is kept, so a later start() reuses it."""
    global _worker
    with _worker_lock:
        if _worker is not None and _worker.stop(timeout):
            _worker = None


@click.command("learning-worker")
@with_appcontext
def learning_worker_command():
    """Run Learning AI replies in the foreground, for a separate worker process."""
    app = current_app._get_current_object()
    provider = provider_for(app)
    if provider is None:
        raise click.ClickException("No Learning AI provider is available in this release.")
    Worker(app, provider).run_forever()
