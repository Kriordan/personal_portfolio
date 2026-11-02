"""Real templates, native form POSTs, and reply polling in headless Chrome.

Uses the existing Chrome CLI test approach, a disposable SQLite database, and the
scripted provider. No browser library, paid provider, or production server is used.
PostgreSQL migration/concurrency tests remain in their dedicated suites.
"""
from contextlib import ExitStack
from html import unescape
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
from threading import Thread
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from uuid import uuid4

from flask import jsonify, request, send_file
from flask_login import login_user
from sqlalchemy import event
from sqlalchemy.exc import OperationalError
from werkzeug.serving import WSGIRequestHandler, make_server

from project import create_app
from project.database import db
from project.extensions import talisman
from project.models import ArtifactRevision, SessionMessage, User
from project.services import practice_service as practice, practice_worker
from tests.test_practice_service import enable_sqlite_foreign_keys, seed_catalog

ROOT = Path(__file__).resolve().parents[1]
CHROME = os.environ.get("CHROME_BIN") or shutil.which("google-chrome") or (
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
    if Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome").exists() else None)


class QuietHandler(WSGIRequestHandler):
    def log(self, *_args, **_kwargs):
        pass


class PracticeBrowserTests(unittest.TestCase):
    def test_workspace_navigation_saving_recovery_and_reply_continuity(self):
        if not CHROME:
            if os.environ.get("CI"):
                self.fail("Chrome is required for the practice browser regression in CI")
            self.skipTest("Install Chrome or set CHROME_BIN to run the practice browser regression")
        with tempfile.TemporaryDirectory(prefix="practice-browser-") as directory, ExitStack() as stack:
            app = create_app(dict(TESTING=True, SECRET_KEY="browser-fixture",
                SQLALCHEMY_DATABASE_URI=f"sqlite:///{Path(directory) / 'fixture.sqlite'}",
                WTF_CSRF_ENABLED=True, SESSION_COOKIE_SECURE=False, RATELIMIT_ENABLED=False,
                LEARNING_PRACTICE_ENABLED=True, LEARNING_AI_ENABLED=False,
                LEARNING_AI_PROVIDER="fake", LEARNING_AI_OWNER_EMAIL="fixture1@example.test"))
            talisman.force_https = False
            with app.app_context():
                event.listen(db.engine, "connect", enable_sqlite_foreign_keys)
                db.engine.dispose()
                db.create_all()
                user = User(id=1, username="Browser fixture", email="fixture1@example.test", email_verified=True)
                db.session.add(user)
                db.session.commit()
                seed_catalog(SimpleNamespace())
                session_id = practice.start_session(user, exercise_id="idempotent-order-api",
                                                   request_id=str(uuid4()))["session_id"]
                # Enough saved history to exercise scrolling away from the newest turn.
                for number in range(8):
                    practice.send_turn(user, session_id, body=f"Earlier reasoning {number}: " + "A retry may arrive later. " * 12,
                        expected_sequence=number + 1, artifact_revisions={"api": 0, "schema": 0, "algorithm": 0},
                        brief_revision=0, request_id=str(uuid4()))
            app.config["LEARNING_AI_ENABLED"] = True
            failure = {"mode": "success"}

            def fail_or_lose(operation):
                def wrapped(*args, **kwargs):
                    if failure["mode"] == "failure":
                        raise OperationalError("fixture", {}, Exception("Fixture database unavailable"))
                    result = operation(*args, **kwargs)
                    if failure["mode"] == "lost":
                        raise OperationalError("fixture", {}, Exception("Fixture lost response after commit"))
                    return result
                return wrapped

            for name in ("save_work", "save_and_send", "send_turn", "request_reply"):
                stack.enter_context(patch.object(practice, name, fail_or_lose(getattr(practice, name))))

            @app.get("/__browser_checks__")
            def checks():
                login_user(db.session.get(User, 1))
                return ('<!doctype html><meta charset="utf-8"><title>Practice browser checks</title>'
                        '<pre id="result">Running</pre><iframe id="workspace" title="Practice workspace" '
                        f'style="width:1280px;height:720px;border:0" src="/learning/practice/{session_id}"></iframe>'
                        '<script src="/__browser_script__"></script>')

            @app.get("/__browser_script__")
            def script():
                return send_file(ROOT / "tests/browser/practice-workspace-checks.js", mimetype="application/javascript")

            @app.post("/__browser_control__")
            def control():
                values = request.get_json()
                if "mode" in values:
                    failure["mode"] = values["mode"]
                if values.get("reply"):
                    practice_worker.run_once(practice_worker.FakeProvider(replies=[
                        "What happens if two requests arrive at the same time? Explain your reasoning."]))
                return jsonify(revisions=ArtifactRevision.query.count(),
                    learner_turns=SessionMessage.query.filter_by(role="learner", kind="turn").count(),
                    interviewer_turns=SessionMessage.query.filter_by(role="interviewer", kind="turn").count())

            @app.after_request
            def local_only(response):
                # No external fonts/scripts during tests. Allows same-origin frames
                # and the test harness, without changing the production CSP.
                response.headers["Content-Security-Policy"] = (
                    "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'")
                if request.args.get("fixture_storage") == "blocked" and response.mimetype == "text/html":
                    response.set_data(response.get_data(as_text=True).replace("</head>",
                        '<script>for (const key of ["localStorage","sessionStorage"]) '
                        'Object.defineProperty(window,key,{get(){throw new Error("Storage blocked");}});</script></head>'))
                return response

            # Run after Talisman so the local-only policy is actually enforced.
            app.after_request_funcs[None].remove(local_only)
            app.after_request_funcs[None].insert(0, local_only)
            self.assertEqual(app.test_client().get("/learning/").headers["Content-Security-Policy"],
                "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'")

            server = make_server("127.0.0.1", 0, app, threaded=True, request_handler=QuietHandler)
            thread = Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                completed = subprocess.run([CHROME, "--headless", "--disable-gpu", "--no-first-run",
                    "--no-default-browser-check", *(["--no-sandbox"] if os.environ.get("CI") else []),
                    f"--user-data-dir={Path(directory) / 'chrome'}", "--dump-dom", "--virtual-time-budget=180000",
                    f"http://127.0.0.1:{server.server_port}/__browser_checks__"],
                    capture_output=True, text=True, timeout=55)
                self.assertEqual(completed.returncode, 0, completed.stderr[-2000:])
                result = re.search(r'<pre id="result">(.*?)</pre>', completed.stdout, re.S)
                self.assertIsNotNone(result, completed.stdout[-2000:])
                report = unescape(result.group(1))
                self.assertIn('data-test-result="pass"', completed.stdout, report)
                print(report)
            finally:
                server.shutdown()
                thread.join(timeout=5)
                server.server_close()
                with app.app_context():
                    db.session.remove()
                    db.engine.dispose()
