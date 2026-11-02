"""Real hub/library navigation and saved progress in Chrome; no paid AI calls."""
from contextlib import ExitStack
from functools import partial
from html import unescape
import os
from pathlib import Path
import re
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
from werkzeug.serving import make_server

from project import create_app
from project.database import db
from project.extensions import talisman
from project.models import ArtifactRevision, PracticeSession, ReviewLog, ReviewReceipt, SessionMessage, User
from project.services import learning_service, practice_service
from tests.learning_hub_fixtures import seed_notes
from tests.test_practice_browser import CHROME, QuietHandler, ROOT
from tests.test_practice_service import enable_sqlite_foreign_keys, seed_catalog


class LearningHubBrowserTests(unittest.TestCase):
    def test_destinations_resume_review_and_responsive_navigation(self):
        self.run_browser_checks("learning-hub-checks.js")

    def test_concept_modes_keep_the_selected_session_and_review_attempt(self):
        self.run_browser_checks("concept-workspace-checks.js")

    def run_browser_checks(self, script_name):
        if not CHROME:
            if os.environ.get("CI"):
                self.fail("Chrome is required for the Learning hub regression in CI")
            self.skipTest("Install Chrome or set CHROME_BIN to run the Learning hub regression")
        with tempfile.TemporaryDirectory(prefix="hub-browser-") as directory, ExitStack() as stack:
            app = create_app(dict(TESTING=True, SECRET_KEY="hub-browser-fixture",
                SQLALCHEMY_DATABASE_URI=f"sqlite:///{Path(directory) / 'fixture.sqlite'}",
                WTF_CSRF_ENABLED=True, SESSION_COOKIE_SECURE=False, RATELIMIT_ENABLED=False,
                LEARNING_PRACTICE_ENABLED=True, LEARNING_AI_ENABLED=False, LEARNING_AI_PROVIDER="fake"))
            talisman.force_https = False
            notes = Path(directory) / "notes"
            stack.enter_context(patch.object(learning_service, "notes_dir_for_root", return_value=notes))
            stack.enter_context(patch.object(learning_service, "build_review_queue",
                side_effect=partial(learning_service.build_review_queue, seed=7)))
            with app.app_context():
                event.listen(db.engine, "connect", enable_sqlite_foreign_keys)
                db.engine.dispose()
                db.create_all()
                user = User(id=1, username="Hub fixture", email="hub@example.test", email_verified=True)
                db.session.add(user)
                db.session.commit()
                seed_catalog(SimpleNamespace())
                seed_notes(notes)
                session_id = practice_service.start_session(user, exercise_id="idempotent-order-api",
                    request_id=str(uuid4()))["session_id"]
                practice_service.save_work(user, session_id, status="paused", request_id=str(uuid4()),
                    edits=[dict(artifact_id="api", language="text", body="POST /orders — saved work", base_revision=0)])
                if script_name == "concept-workspace-checks.js":
                    # Navigation must keep this older session, even with a newer one available.
                    practice_service.start_session(user, exercise_id="idempotent-order-api", request_id=str(uuid4()))

            @app.get("/__hub_checks__")
            def checks():
                login_user(db.session.get(User, 1))
                initial = (f"/learning/concepts/idempotency?practice_session={session_id}"
                           if script_name == "concept-workspace-checks.js" else "/learning/")
                return ('<!doctype html><meta charset="utf-8"><title>Learning hub checks</title>'
                        '<pre id="result">Running</pre><iframe id="hub" title="Learning pages" '
                        f'style="width:1280px;height:800px;border:0" src="{initial}"></iframe>'
                        '<script src="/__hub_script__"></script>')

            @app.get("/__hub_script__")
            def script():
                return send_file(ROOT / "tests/browser" / script_name, mimetype="application/javascript")

            @app.get("/__hub_counts__")
            def counts():
                return jsonify(sessions=PracticeSession.query.count(), artifacts=ArtifactRevision.query.count(),
                    ratings=ReviewLog.query.count(), receipts=ReviewReceipt.query.count(),
                    turns=SessionMessage.query.filter_by(kind="turn").count())

            @app.after_request
            def local_only(response):
                scripts = "'none'" if request.args.get("fixture_scripts") == "off" else "'self' 'unsafe-inline'"
                response.headers["Content-Security-Policy"] = (
                    f"default-src 'self'; script-src {scripts}; style-src 'self' 'unsafe-inline'")
                return response

            # Flask runs after_request handlers in reverse registration order.
            # Apply the fixture CSP after Talisman, which otherwise replaces it.
            app.after_request_funcs[None].remove(local_only)
            app.after_request_funcs[None].insert(0, local_only)
            self.assertEqual(app.test_client().get("/learning/?fixture_scripts=off").headers["Content-Security-Policy"],
                "default-src 'self'; script-src 'none'; style-src 'self' 'unsafe-inline'")

            server = make_server("127.0.0.1", 0, app, threaded=True, request_handler=QuietHandler)
            thread = Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                completed = subprocess.run([CHROME, "--headless", "--disable-gpu", "--no-first-run",
                    "--no-default-browser-check", *(["--no-sandbox"] if os.environ.get("CI") else []),
                    f"--user-data-dir={Path(directory) / 'chrome'}", "--dump-dom", "--virtual-time-budget=120000",
                    f"http://127.0.0.1:{server.server_port}/__hub_checks__"],
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
