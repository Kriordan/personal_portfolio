"""The Learning reply worker: one tracked thread in the web process, or a process of its own.

Replies are database rows with leases, so a restart loses nothing: a stale reply reads as
interrupted and the learner asks again. Paid calls are never retried automatically. Each
provider call goes through an injectable provider: the scripted FakeProvider here, and in
checkpoint 4b a short-lived child process, so a stuck call can always be abandoned.
Logs and error reports carry fixed codes only, never learner text or model output.
"""
from __future__ import annotations

import json
import os
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

FAKE_MODES = ("success", "slow", "fail", "lost", "hang", "invalid")
# Expected outcomes that are logged but not reported as errors.
QUIET_CODES = {"budget", "unpriced"}


class ProviderError(Exception):
    """A provider call that produced no usable reply.

    `charged` says what the ledger records: "no" releases the reservation, "yes" settles it
    (from `usage` when known), and "unknown" leaves it reserved as an uncertain cost.
    """

    def __init__(self, code, *, charged="unknown", usage=None):
        super().__init__(code)
        self.code, self.charged, self.usage = code, charged, usage


class FakeProvider:
    """Scripted replies for tests and the preview fixture. It never contacts a network.

    `mode` may be a callable, so a running fixture can switch it: success, slow, fail
    (refused before any paid work), lost (outcome unknown), hang (until the deadline), or
    invalid (an empty reply).
    """

    def __init__(self, mode="success", *, delay=2.0, replies=()):
        self.mode, self.delay, self.replies, self.calls = mode, delay, list(replies), []

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
        reply = "" if mode == "invalid" else (
            self.replies.pop(0) if self.replies else "What should happen when the same order request arrives twice?")
        size = len(json.dumps(body, ensure_ascii=False).encode("utf-8"))
        return {"output": {"reply": reply},
                "usage": {"input_tokens": size // 4, "cached_input_tokens": 0, "output_tokens": max(len(reply) // 4, 1)}}


def provider_for(app):
    """The configured provider, or None when this release can't call it."""
    if app.config.get("LEARNING_AI_PROVIDER", "openai") == "fake":
        return FakeProvider(app.config.get("LEARNING_AI_FAKE_MODE", "success"))
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
    context = practice_service.reply_context(reply_id)
    if context is None:
        return
    settings = practice_service.ai_settings()
    body = interviewer.reply_request(context, settings)
    try:
        charge = practice_service.begin_call(reply_id, token, purpose="reply", input_bytes=interviewer.body_bytes(body),
                                             max_output_tokens=body["max_output_tokens"],
                                             deadline_seconds=settings["call_seconds"], now=now())
    except practice_service.CallFenced:
        return
    except practice_budget.BudgetExhausted as exc:
        _report(exc.code, reply_id)
        return
    try:
        result = provider.call(body, deadline=settings["call_seconds"])
    except ProviderError as error:
        outcome = {"no": "released", "yes": "settled"}.get(error.charged, "uncertain")
        practice_service.finish_call(charge, outcome=outcome, usage=error.usage, now=now())
        practice_service.fail_reply(reply_id, token, code=error.code, now=now())
        _report(error.code, reply_id)
        return
    practice_service.finish_call(charge, outcome="settled", usage=result.get("usage"), now=now())
    output = result.get("output")
    _complete(reply_id, token, output.get("reply") if isinstance(output, dict) else None, now)


def _complete(reply_id, token, reply, now):
    """Write the reply, retrying the database write (never the paid call) on transient errors."""
    for attempt in range(3):
        try:
            if practice_service.complete_reply(reply_id, token, body=reply, now=now()) == "invalid":
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
