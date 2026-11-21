"""Fresh migration and physical backup/restore on dedicated local PostgreSQL databases."""
from pathlib import Path
from copy import deepcopy
from datetime import datetime, timezone
import json
import os
import socket
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch
from uuid import uuid4

from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from flask_migrate import upgrade
import psycopg
import requests
from psycopg import sql
from sqlalchemy.engine import make_url

from project import create_app
from project.database import db
from project.models import User, ReviewProgress, ContentRevision
from project.services import concept_progress_service as progress, self_assessment_service as assessment, practice_service
from project.services import curriculum_service as curriculum
from project.services.learning_service import NotFoundError
from scripts import learning_pilot_storage as storage
from scripts import learning_pilot as pilot
from tests.test_concept_progress import position
from tests.test_self_assessment import checkin
from tests.test_practice_service import seed_catalog
from tests.test_practice_web import FormFields, as_browser

URL = os.environ.get("LIBRARY_TEST_POSTGRES_URL")
ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(URL, "Set LIBRARY_TEST_POSTGRES_URL to the isolated test database")
class PilotStoragePostgresTests(unittest.TestCase):
    def setUp(self):
        source = make_url(URL)
        if source.host not in {"127.0.0.1", "localhost"} or source.database != "library_sync_test":
            raise RuntimeError("Refusing fixtures outside the isolated local test server")
        self.created = []
        self.source = source

    def target(self):
        url = self.source.set(database="learning_pilot_test_" + uuid4().hex[:12])
        instance = str(uuid4())
        self.created.append((url, instance))
        return url.render_as_string(hide_password=False), instance

    def app(self, value):
        return create_app(dict(TESTING=True, SECRET_KEY="fixture", SQLALCHEMY_DATABASE_URI=value,
                               LEARNING_PRACTICE_ENABLED=True, LEARNING_AI_ENABLED=False))

    def initialize(self, directory, *, port=5068):
        value, _ = self.target()
        try:
            return pilot.initialize(directory, database_url=value, email="learner@example.com", port=port)
        finally:
            settings_file = directory / pilot.SETTINGS
            if settings_file.exists():
                settings = storage.read_json(settings_file)
                self.created[-1] = (make_url(value), settings["instance_id"])

    def tearDown(self):
        for url, instance in self.created:
            with psycopg.connect(**storage.connect_args(url, admin=True), autocommit=True) as connection:
                marker = connection.execute("SELECT shobj_description(oid, 'pg_database') FROM pg_database WHERE datname = %s", (url.database,)).fetchone()
                if marker:
                    self.assertEqual(marker[0], storage.database_marker(instance))
                    connection.execute(sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(url.database)))

    @patch("logging.config.fileConfig")
    def test_full_migration_restart_and_backup_restore_preserve_learning_data(self, _logging):
        value, instance = self.target()
        storage.create_database(value, instance)
        app = self.app(value)
        with app.app_context():
            upgrade(directory=str(ROOT / "migrations"))
            with db.engine.connect() as connection:
                self.assertEqual(compare_metadata(MigrationContext.configure(connection), db.metadata), [])
            db.session.add(User(id=1, username="fixture", email="pilot@example.com", email_verified=True))
            db.session.commit()
            seed_catalog(self)
            progress.enroll(1, "idempotency")
            bookmark = progress.save_position(1, "idempotency", **position())
            reflection = assessment.save(1, "idempotency", **checkin(recognition="with_help"))
            user = db.session.get(User, 1)
            session_id = practice_service.start_session(user, exercise_id="idempotent-order-api", request_id=str(uuid4()))["session_id"]
            practice_service.save_work(user, session_id, request_id=str(uuid4()), status="paused",
                edits=[dict(artifact_id="api", base_revision=0, language="text", body="Persistent API outline")])
            detail = practice_service.session_detail(1, session_id)
            db.session.remove()
            db.engine.dispose()
        with tempfile.TemporaryDirectory() as folder:
            dump = Path(folder) / "pilot.dump"
            checksum = storage.dump_database(value, instance, dump)
            self.assertEqual(dump.stat().st_mode & 0o777, 0o600)
            restored, restored_instance = self.target()
            storage.restore_database(restored, restored_instance, dump, checksum)
            for destination in (value, restored):
                # Fresh application/engine, no carried ORM identity map or in-memory data.
                with self.app(destination).app_context():
                    self.assertEqual(progress.progress(1, "idempotency"), bookmark)
                    self.assertEqual(assessment.history(1, "idempotency")["current"], reflection)
                    self.assertEqual(practice_service.session_detail(1, session_id), detail)
                    self.assertEqual(ReviewProgress.query.count(), 0)
                    db.session.remove()
                    db.engine.dispose()

    def test_existing_database_wrong_identity_and_corrupt_backup_are_refused(self):
        value, instance = self.target()
        storage.create_database(value, instance)
        with self.assertRaises(storage.PilotError):
            storage.create_database(value, instance)
        with self.assertRaises(storage.PilotError):
            storage.verify_database(value, str(uuid4()))
        self.assertEqual(storage.verify_database(value, instance).database, make_url(value).database)
        with tempfile.TemporaryDirectory() as folder:
            backup = Path(folder) / "invalid.dump"
            storage.write_private(backup, "incomplete backup")
            other, other_instance = self.target()
            with self.assertRaises(storage.PilotError):
                storage.restore_database(other, other_instance, backup, "incorrect checksum")
            url = make_url(other)
            with psycopg.connect(**storage.connect_args(url, admin=True)) as connection:
                self.assertIsNone(connection.execute("SELECT 1 FROM pg_database WHERE datname = %s", (url.database,)).fetchone())

    @patch("logging.config.fileConfig")
    def test_local_runtime_requires_login_and_csrf_ignores_ambient_configuration_and_survives_restart(self, _logging):
        with tempfile.TemporaryDirectory() as folder:
            directory = Path(folder) / "pilot"
            settings = self.initialize(directory)
            with patch.dict(os.environ, DATABASE_URL="postgresql://remote/portfolio", LEARNING_AI_ENABLED="true",
                            SENTRY_ENABLED="true", SECRET_KEY="wrong", OPENAI_API_KEY="never-use-this"):
                app = pilot.app_for(settings)
            self.assertFalse(app.config["LEARNING_AI_ENABLED"])
            self.assertFalse(app.config["SENTRY_ENABLED"])
            self.assertEqual(app.config["SQLALCHEMY_DATABASE_URI"], settings["database_url"])
            self.assertEqual(app.config["SECRET_KEY"], settings["secret_key"])
            self.assertTrue(app.config["WTF_CSRF_ENABLED"])
            client = app.test_client()
            self.assertEqual(client.get("/learning/").status_code, 302)
            response = client.get("/login")
            html = response.get_data(as_text=True)
            self.assertIn("Personal local Learning pilot", html)
            self.assertNotIn("googletagmanager.com", html)
            self.assertNotIn("static.hotjar.com", html)
            self.assertNotIn('href="/forgot-password"', html)
            self.assertNotIn('href="/resume"', html)
            self.assertEqual(response.headers["Cache-Control"], "private, no-store")
            self.assertIn(settings["instance_id"].split("-")[0], response.headers["Set-Cookie"])
            self.assertNotIn("; Secure", response.headers["Set-Cookie"])
            self.assertIn("; HttpOnly", response.headers["Set-Cookie"])
            password = (directory / "login.txt").read_text().split("Password: ", 1)[1].strip()
            client.post("/login", data={"email": settings["owner_email"], "password": password})
            self.assertEqual(client.get("/learning/").status_code, 302)  # missing CSRF never logs in
            fields = FormFields(client.get("/login").get_data(as_text=True)).values
            response = client.post("/login", data={"email": settings["owner_email"], "password": password,
                                                   "csrf_token": fields["csrf_token"]})
            self.assertEqual(response.status_code, 302)
            self.assertEqual(client.get("/learning/").status_code, 200)
            cookie_name = app.config["SESSION_COOKIE_NAME"]
            cookie = client.get_cookie(cookie_name).value
            self.assertEqual(client.get("/pilot/health").get_json(), {"status": "ok", "ai_enabled": False})
            self.assertEqual(client.get("/pilot/health", environ_overrides={"REMOTE_ADDR": "192.0.2.1"}).status_code, 403)
            self.assertEqual(client.get("/pilot/health", base_url="http://attacker.example").status_code, 400)
            for path in ("/signup", "/forgot-password", "/api/v1/library/sync", "/fixture/reset"):
                self.assertEqual(client.post(path).status_code, 404)
            with app.app_context():
                original_hash = db.session.scalar(db.select(User)).password_hash
                db.session.remove()
                db.engine.dispose()
            # Same settings create a new engine and session signer, retaining login.
            restarted = pilot.app_for(pilot.load_settings(directory))
            client = restarted.test_client()
            client.set_cookie(cookie_name, cookie)
            self.assertEqual(client.get("/learning/").status_code, 200)
            with restarted.app_context():
                pilot.check_schema()
                self.assertEqual(db.session.scalar(db.select(User)).password_hash, original_hash)
                db.session.remove()
                db.engine.dispose()
            with self.assertRaises(FileExistsError):
                pilot.initialize(directory, database_url=settings["database_url"], email=settings["owner_email"], port=5068)

    @patch("logging.config.fileConfig")
    def test_interrupted_setup_is_explicitly_resumable_and_restore_uses_new_identity(self, _logging):
        with tempfile.TemporaryDirectory() as folder:
            directory = Path(folder) / "pilot"
            with patch.object(pilot, "finish_initialization", side_effect=RuntimeError("interrupted")):
                with self.assertRaises(RuntimeError):
                    self.initialize(directory)
            original = pilot.load_settings(directory)
            login = (directory / "login.txt").read_text()
            pilot.resume_initialization(directory)
            pilot.resume_initialization(directory)  # repeat never duplicates/reset accounts
            self.assertEqual(pilot.load_settings(directory), original)
            self.assertEqual((directory / "login.txt").read_text(), login)
            with pilot.app_for(original).app_context():
                self.assertEqual(User.query.count(), 1)
                db.session.remove()
                db.engine.dispose()
            with storage.operator_lock(directory), self.assertRaises(storage.PilotError):
                pilot.backup(directory, Path(folder) / "locked")
            backup = pilot.backup(directory, Path(folder) / "backup")
            value, _ = self.target()
            restored_directory = Path(folder) / "restored"
            restored = pilot.restore(backup, restored_directory, value)
            self.created[-1] = (make_url(value), restored["instance_id"])
            self.assertTrue(restored["restored"])
            for key in ("instance_id", "secret_key", "jwt_secret_key"):
                self.assertNotEqual(restored[key], original[key])
            self.assertEqual((restored_directory / "login.txt").read_text(), login)
            with pilot.app_for(restored).app_context():
                pilot.check_schema()
                self.assertEqual(User.query.count(), 1)
                db.session.remove()
                db.engine.dispose()
            with self.assertRaises(storage.PilotError):
                pilot.resume_initialization(restored_directory)

    @patch("logging.config.fileConfig")
    def test_cli_process_restart_keeps_login_and_saved_work(self, _logging):
        with socket.socket() as available:
            available.bind(("127.0.0.1", 0))
            port = available.getsockname()[1]
        with tempfile.TemporaryDirectory() as folder, requests.Session() as browser:
            directory = Path(folder) / "pilot"
            settings = self.initialize(directory, port=port)
            with pilot.app_for(settings).app_context():
                seed_catalog(self)
                user = db.session.scalar(db.select(User))
                session_id = practice_service.start_session(user, exercise_id="idempotent-order-api", request_id=str(uuid4()))["session_id"]
                practice_service.save_work(user, session_id, request_id=str(uuid4()), status="paused",
                    edits=[dict(artifact_id="api", base_revision=0, language="text", body="Saved before a real process restart")])
                db.session.remove()
                db.engine.dispose()
            url = f"http://127.0.0.1:{port}"
            command = [sys.executable, str(ROOT / "scripts/learning-pilot.py"), "--state-dir", str(directory), "serve"]
            for restart in range(2):
                child = subprocess.Popen(command, cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                try:
                    deadline = time.monotonic() + 15
                    while True:
                        self.assertIsNone(child.poll(), "Pilot exited before becoming ready")
                        try:
                            response = browser.get(url + "/pilot/health", timeout=1)
                            if response.status_code == 200:
                                break
                        except requests.ConnectionError:
                            pass
                        if time.monotonic() > deadline:
                            self.fail("Pilot did not become ready")
                        time.sleep(.05)
                    self.assertFalse(response.json()["ai_enabled"])
                    if restart == 0:
                        form = FormFields(browser.get(url + "/login", timeout=5).text).values
                        password = (directory / "login.txt").read_text().split("Password: ", 1)[1].strip()
                        response = browser.post(url + "/login", data={"csrf_token": form["csrf_token"],
                            "email": settings["owner_email"], "password": password}, timeout=5)
                        self.assertEqual(response.status_code, 200)
                    response = browser.get(url + f"/learning/practice/{session_id}?view=build", timeout=5)
                    self.assertEqual(response.status_code, 200)
                    self.assertIn("Saved before a real process restart", response.text)
                    self.assertNotIn("/login", response.url)
                    with self.assertRaises(storage.PilotError):
                        pilot.backup(directory, Path(folder) / "blocked-backup")
                finally:
                    child.terminate()
                    try:
                        child.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        child.kill()
                        child.wait(timeout=5)

    @patch("logging.config.fileConfig")
    def test_exact_local_drafts_are_labelled_and_private_evaluation_stays_server_side(self, _logging):
        with tempfile.TemporaryDirectory() as folder:
            directory = Path(folder) / "pilot"
            settings = self.initialize(directory)
            consent = pilot.authorize(directory, total_usd="5", verification_usd="1", allow_draft=True)
            self.assertEqual(consent, pilot.authorize(directory, total_usd="5", verification_usd="1", allow_draft=True))
            with self.assertRaises(storage.PilotError):
                pilot.authorize(directory, total_usd="6", verification_usd="1", allow_draft=True)
            self.assertEqual(pilot.load_approval(directory, settings), consent)
            app = pilot.app_for(settings, approval=consent)
            with app.app_context():
                self.assertTrue(curriculum.published_learner_item("idempotency")["local_draft"])
                self.assertTrue(curriculum.published_concepts()[0]["local_draft"])
                self.assertEqual(curriculum.published_learner_item("idempotency")["version"], 2)
                exercise = curriculum.published_learner_item("idempotent-order-api")
                self.assertEqual(exercise["version"], 3)
                for private in ("assessment", "facilitator", "reference_reasoning", "rubric", "hidden_constraints"):
                    self.assertNotIn('"' + private + '"', json.dumps(exercise))
                self.assertEqual(ContentRevision.query.filter(ContentRevision.published_at.is_not(None)).count(), 0)
                self.assertTrue(all(row.reviewed_by is None and row.reviewed_on is None for row in ContentRevision.query.all()))
                sid = practice_service.start_session(db.session.scalar(db.select(User)), exercise_id="idempotent-order-api",
                                                     request_id=str(uuid4()))["session_id"]
                # An unapproved newer version cannot replace the exact allowed revision.
                original = db.session.get(ContentRevision, ("idempotency", 2))
                newer = deepcopy(original.payload)
                newer["version"] = 3
                db.session.add(ContentRevision(item_id="idempotency", version=3, schema_version=original.schema_version,
                    payload=newer, checksum=curriculum.content_checksum(newer, original.schema_version), imported_at=datetime.now(timezone.utc)))
                db.session.commit()
                self.assertEqual(curriculum.published_learner_item("idempotency")["version"], 2)
                original_checksum = original.checksum
                original.checksum = "f" * 64
                db.session.commit()
                self.assertIsNone(curriculum.published_learner_item("idempotency"))
                original.checksum = original_checksum
                db.session.commit()
                with patch.dict(app.config, LEARNING_LOCAL_PILOT=False):
                    self.assertIsNone(curriculum.published_learner_item("idempotency"))
                    with self.assertRaises(NotFoundError):
                        practice_service._published_exercise("idempotent-order-api")
                db.session.remove()
                db.engine.dispose()
            client = app.test_client()
            with client.session_transaction() as session:
                session["_user_id"] = "1"
                session["_fresh"] = True
            for path in ("/learning/concepts/idempotency", f"/learning/practice/{sid}?view=build"):
                response = client.get(path)
                self.assertEqual(response.status_code, 200)
                self.assertIn(b"Draft idempotency content", response.data)
                self.assertEqual(response.headers["X-Learning-Content-Status"], "local-draft-pilot")
                for private in (b'"reference_reasoning"', b'"hidden_constraints"', b'"rubric"'):
                    self.assertNotIn(private, response.data)
            fields = FormFields(response.get_data(as_text=True)).values
            fields["action"] = "pause"
            paused = client.post(f"/learning/practice/{sid}", data=as_browser(fields), follow_redirects=True)
            self.assertIn(b"resume it from Learning on this computer", paused.data)
            with app.app_context():
                db.session.remove()
                db.engine.dispose()
            # The ordinary reader of the same DB still sees no published concept.
            with self.app(settings["database_url"]).app_context():
                self.assertIsNone(curriculum.published_learner_item("idempotency"))
                self.assertEqual(curriculum.published_concepts(), [])
                db.session.remove()
                db.engine.dispose()

    @patch("logging.config.fileConfig")
    def test_live_activation_verification_cap_and_restore_cannot_reauthorize_spending(self, _logging):
        with tempfile.TemporaryDirectory() as folder:
            directory = Path(folder) / "pilot"
            settings = self.initialize(directory)
            with self.assertRaises(storage.PilotError):
                pilot.app_for(settings, live=True)
            consent = pilot.authorize(directory, total_usd="5", verification_usd="1", allow_draft=True)
            offline = pilot.app_for(settings, approval=consent)
            self.assertFalse(offline.config["LEARNING_AI_ENABLED"])
            verification = pilot.app_for(settings, approval=consent, live=True, verification=True)
            self.assertEqual(verification.config["LEARNING_AI_TOTAL_CAP_USD"], 1)
            self.assertEqual(pilot.app_for(settings, approval=consent, live=True).config["LEARNING_AI_TOTAL_CAP_USD"], 5)
            with patch.object(pilot, "make_server", side_effect=OSError("port busy")), patch.object(pilot, "learning_key") as key:
                with patch.object(pilot.practice_worker, "start") as worker, patch.object(pilot.signal, "signal"):
                    with self.assertRaises(OSError):
                        pilot.serve(directory, live=True, verification=True)
                    key.assert_not_called()
                    worker.assert_not_called()
            backup = pilot.backup(directory, Path(folder) / "backup")
            value, _ = self.target()
            restored_directory = Path(folder) / "restored"
            restored = pilot.restore(backup, restored_directory, value)
            self.created[-1] = (make_url(value), restored["instance_id"])
            restored_consent = pilot.load_approval(restored_directory, restored)
            restored_app = pilot.app_for(restored, approval=restored_consent)
            with restored_app.app_context():
                self.assertIsNotNone(curriculum.published_learner_item("idempotency"))
                self.assertFalse(restored_app.config["LEARNING_AI_ENABLED"])
                db.session.remove()
                db.engine.dispose()
            with self.assertRaises(storage.PilotError):
                pilot.app_for(restored, approval=restored_consent, live=True)
            with self.assertRaises(storage.PilotError):
                pilot.authorize(restored_directory, total_usd="5", verification_usd="1", allow_draft=True)
