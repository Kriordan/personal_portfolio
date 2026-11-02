"""Real PostgreSQL publication races, failure recovery, and additive migration."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import date
import json
import os
from pathlib import Path
import select as io_select
import subprocess
import sys
import tempfile
from threading import Barrier
import unittest
from unittest.mock import patch
from uuid import uuid4

from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from flask_migrate import downgrade, stamp, upgrade
from marshmallow import ValidationError
from sqlalchemy import text
from sqlalchemy.engine import make_url

from project import create_app
from project.curriculum_terms import ARTIFACT_FORMATS, ARTIFACT_LANGUAGES, INTERACTION_STYLES
from project.database import db
from project.learning.content_schema import load_catalog
from project.models import ContentRevision, CurriculumItem, ReviewLog, ReviewProgress, ReviewReceipt, User
from project.services import curriculum_service as service
from project.services import feedback_service, practice_service, practice_worker
from project.services.learning_service import rate_card_for_user
from tests.curriculum_v2_fixtures import CATALOG_V2

URL = os.environ.get("LIBRARY_TEST_POSTGRES_URL")
ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "curriculum/idempotency/catalog.json"
REVIEW = dict(publish=True, reviewed_by="Fixture reviewer", reviewed_on=date(2026, 10, 1))


@unittest.skipUnless(URL, "Set LIBRARY_TEST_POSTGRES_URL to the isolated local test database")
class CurriculumPostgresTests(unittest.TestCase):
    def setUp(self):
        url = make_url(URL)
        if url.host not in {"localhost", "127.0.0.1"} or url.database != "library_sync_test":
            raise RuntimeError("Refusing destructive fixtures outside the isolated local test database")
        self.config = dict(TESTING=True, SECRET_KEY="fixture", SQLALCHEMY_DATABASE_URI=URL)
        self.app = create_app(self.config)
        self.context = self.app.app_context()
        self.context.push()
        db.create_all()
        self.catalog = load_catalog(CATALOG)

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        with db.engine.begin() as connection:
            connection.execute(text("DROP TABLE IF EXISTS alembic_version"))
        db.engine.dispose()
        self.context.pop()

    def test_dry_run_and_publication_requirements(self):
        report = service.import_catalog(self.catalog, **REVIEW)
        self.assertEqual(report, dict(items=6, inserted=6, published=6, dry_run=True))
        self.assertEqual(CurriculumItem.query.count(), 0)
        self.assertEqual(ContentRevision.query.count(), 0)
        with self.assertRaises(ValidationError):
            service.import_catalog(self.catalog, dry_run=False, publish=True)
        self.assertEqual(CurriculumItem.query.count(), 0)

    def test_drafts_publication_replay_and_version_pinning(self):
        service.import_catalog(self.catalog, dry_run=False)
        self.assertIsNone(service.published_learner_item("idempotency"))
        original = db.session.get(ContentRevision, ("idempotency", 1)).checksum
        first = service.import_catalog(self.catalog, dry_run=False, **REVIEW)
        self.assertEqual((first["inserted"], first["published"]), (0, 6))
        replay = service.import_catalog(self.catalog, dry_run=False, **REVIEW)
        self.assertEqual((replay["inserted"], replay["published"]), (0, 0))
        next_version = deepcopy(self.catalog)
        next_version["items"][0].update(version=2, title="Revised title")
        service.import_catalog(next_version, dry_run=False)
        self.assertEqual(service.published_learner_item("idempotency")["version"], 1)
        service.import_catalog(next_version, dry_run=False, **REVIEW)
        self.assertEqual(service.published_learner_item("idempotency")["version"], 2)
        self.assertEqual(service.published_learner_item("idempotency", version=1)["version"], 1)
        db.session.expire_all()
        self.assertEqual(db.session.get(ContentRevision, ("idempotency", 1)).checksum, original)
        self.assertNotIn("assessment", service.published_learner_item("idempotent-order-api")["content"])
        with self.assertRaisesRegex(service.ContentConflict, "behind published"):
            service.import_catalog(self.catalog, dry_run=False, **REVIEW)

    def test_conflict_rolls_back_the_entire_batch(self):
        service.import_catalog(self.catalog, dry_run=False)
        changed = deepcopy(self.catalog)
        extra = deepcopy(changed["items"][0])
        extra["id"] = "aaa-extra"
        extra["content"].update(review_question_ids=[], exercise_ids=[])
        changed["items"].append(extra)
        changed["items"][0]["title"] = "Changed without a new version"
        with self.assertRaisesRegex(service.ContentConflict, "increment its version"):
            service.import_catalog(changed, dry_run=False, **REVIEW)
        self.assertEqual(CurriculumItem.query.count(), 6)
        self.assertEqual(ContentRevision.query.filter(ContentRevision.published_at.is_not(None)).count(), 0)
        self.assertIsNone(db.session.get(CurriculumItem, "aaa-extra"))

    def test_v2_publication_keeps_pinned_sessions_progress_and_old_review_attempts(self):
        service.import_catalog(self.catalog, dry_run=False, **REVIEW)
        user = User(id=1, username="fixture", email="fixture@example.test")
        db.session.add(user)
        db.session.commit()
        start_id = str(uuid4())
        old = practice_service.start_session(user, exercise_id="idempotent-order-api", request_id=start_id)
        session_id = old["session_id"]
        practice_service.save_work(user, session_id, request_id=str(uuid4()), edits=[
            dict(artifact_id="api", base_revision=0, language="text", body="My original API outline")])
        practice_service.send_turn(user, session_id, body="What happens if I lose the reply?",
            expected_sequence=1, artifact_revisions={"api": 1, "schema": 0, "algorithm": 0},
            brief_revision=0, request_id=str(uuid4()))
        practice_service.set_status(user, session_id, status="paused", request_id=str(uuid4()))
        old_detail = practice_service.session_detail(user.id, session_id)
        checksums = {(row.item_id, row.version): row.checksum for row in ContentRevision.query.all()}
        # One committed rating, plus a different still-open v1 attempt when v2 is published.
        rate_card_for_user(user=user, notes_dir=ROOT / "notes", card_id="idempotency:timeout", rating=4,
            request_id=str(uuid4()), expected_revision=0, content_version=1)
        before = {model.__tablename__: [dict(row) for row in db.session.execute(
            model.__table__.select()).mappings()] for model in (ReviewProgress, ReviewLog, ReviewReceipt)}
        open_attempt = dict(user=user, notes_dir=ROOT / "notes", card_id="idempotency:scope", rating=4,
                            request_id=str(uuid4()), expected_revision=0, content_version=1)
        newer = load_catalog(CATALOG_V2)
        self.assertEqual(service.import_catalog(newer)["inserted"], 6)
        self.assertEqual(ContentRevision.query.count(), 6)  # dry run
        service.import_catalog(newer, dry_run=False)
        self.assertEqual(service.published_learner_item("idempotent-order-api")["version"], 1)
        self.assertEqual(service.import_catalog(newer, dry_run=False, **REVIEW)["published"], 6)
        replay = service.import_catalog(newer, dry_run=False, **REVIEW)
        self.assertEqual((replay["inserted"], replay["published"]), (0, 0))
        db.session.expire_all()
        for key, checksum in checksums.items():
            self.assertEqual(db.session.get(ContentRevision, key).checksum, checksum)
        self.assertEqual({row.schema_version for row in ContentRevision.query.filter_by(version=2)}, {2})
        for model in (ReviewProgress, ReviewLog, ReviewReceipt):
            self.assertEqual([dict(row) for row in db.session.execute(model.__table__.select()).mappings()],
                             before[model.__tablename__])
        self.assertEqual(practice_service.session_detail(user.id, session_id), old_detail)
        self.assertEqual(practice_service.start_session(user, exercise_id="idempotent-order-api", request_id=start_id), old)
        latest = practice_service.start_session(user, exercise_id="idempotent-order-api", request_id=str(uuid4()))
        self.assertEqual(latest["exercise_version"], 2)
        first_rating = rate_card_for_user(**open_attempt)
        self.assertEqual(rate_card_for_user(**open_attempt), first_rating)
        self.assertEqual(ReviewLog.query.filter_by(card_id="idempotency:scope").one().content_version, 1)
        self.assertEqual(ReviewReceipt.query.count(), 2)
        current_concept = service.published_learner_item("idempotency")
        self.assertEqual(current_concept["version"], 2)
        self.assertEqual(len(service.concept_review_queue(current_concept, user_id=user.id)), 2)

    def test_v2_mapping_conflict_rolls_back_and_schema_upgrade_cannot_reuse_v1_snapshots(self):
        service.import_catalog(self.catalog, dry_run=False, **REVIEW)
        newer = load_catalog(CATALOG_V2)
        reused = deepcopy(newer)
        reused["items"][0]["version"] = 1
        with self.assertRaisesRegex(service.ContentConflict, "increment its version"):
            service.import_catalog(reused, dry_run=False)
        self.assertEqual(ContentRevision.query.count(), 6)
        service.import_catalog(newer, dry_run=False)
        changed = deepcopy(newer)
        changed["items"][-1]["content"]["assessment"]["misconceptions"][0]["description"] = "Changed mapping"
        extra = deepcopy(changed["items"][0])
        extra["id"] = "aaa-extra"
        extra["content"].update(review_question_ids=[], exercise_ids=[])
        changed["items"].append(extra)
        with self.assertRaisesRegex(service.ContentConflict, "increment its version"):
            service.import_catalog(changed, dry_run=False, **REVIEW)
        self.assertIsNone(db.session.get(CurriculumItem, "aaa-extra"))
        self.assertEqual(ContentRevision.query.count(), 12)
        self.assertEqual(ContentRevision.query.filter(ContentRevision.published_at.is_not(None)).count(), 6)
        stored = db.session.get(ContentRevision, ("idempotent-order-api", 2))
        self.assertEqual(stored.payload, newer["items"][-1])

    def test_simultaneous_v2_publications_cannot_mix_misconception_mappings(self):
        service.import_catalog(self.catalog, dry_run=False, **REVIEW)
        barrier = Barrier(2)

        def publish(label):
            with self.app.app_context():
                catalog = load_catalog(CATALOG_V2)
                for mapping in catalog["items"][-1]["content"]["assessment"]["misconceptions"]:
                    mapping["description"] = label
                barrier.wait(timeout=10)
                try:
                    service.import_catalog(catalog, dry_run=False, **REVIEW)
                    return label
                except service.ContentConflict:
                    return "conflict"

        with ThreadPoolExecutor(2) as pool:
            results = [future.result(timeout=15) for future in
                       [pool.submit(publish, label) for label in ("First", "Second")]]
        self.assertEqual(results.count("conflict"), 1)
        winner = next(result for result in results if result != "conflict")
        stored = db.session.get(ContentRevision, ("idempotent-order-api", 2))
        self.assertEqual({entry["description"] for entry in stored.payload["content"]["assessment"]["misconceptions"]},
                         {winner})
        self.assertEqual(ContentRevision.query.count(), 12)
        self.assertEqual(service.published_learner_item("idempotent-order-api", version=1)["version"], 1)

    def test_omission_does_not_delete_an_existing_identity_or_revision(self):
        service.import_catalog(self.catalog, dry_run=False, **REVIEW)
        reduced = deepcopy(self.catalog)
        reduced["items"] = reduced["items"][:1]
        reduced["items"][0]["version"] = 2
        reduced["items"][0]["content"].update(review_question_ids=[], exercise_ids=[])
        service.import_catalog(reduced, dry_run=False, **REVIEW)
        self.assertEqual(CurriculumItem.query.count(), 6)
        self.assertEqual(ContentRevision.query.count(), 7)
        self.assertIsNotNone(service.published_learner_item("idempotency:timeout", version=1))

    def test_simultaneous_first_publications_commit_one_snapshot(self):
        barrier = Barrier(2)

        def publish():
            with self.app.app_context():
                barrier.wait(timeout=10)
                return service.import_catalog(self.catalog, dry_run=False, **REVIEW)

        with ThreadPoolExecutor(2) as pool:
            futures = [pool.submit(publish) for _ in range(2)]
            reports = [future.result(timeout=15) for future in futures]
        self.assertEqual(sorted(report["inserted"] for report in reports), [0, 6])
        self.assertEqual(sorted(report["published"] for report in reports), [0, 6])
        self.assertEqual(ContentRevision.query.count(), 6)

    def test_simultaneous_conflicting_versions_cannot_mix_content(self):
        barrier = Barrier(2)

        def publish(label):
            with self.app.app_context():
                catalog = deepcopy(self.catalog)
                for item in catalog["items"]:
                    item["title"] = label
                barrier.wait(timeout=10)
                try:
                    service.import_catalog(catalog, dry_run=False, **REVIEW)
                    return label
                except service.ContentConflict:
                    return "conflict"

        with ThreadPoolExecutor(2) as pool:
            futures = [pool.submit(publish, label) for label in ("First", "Second")]
            results = [future.result(timeout=15) for future in futures]
        self.assertEqual(results.count("conflict"), 1)
        winner = next(result for result in results if result != "conflict")
        self.assertEqual({r.payload["title"] for r in ContentRevision.query.all()}, {winner})
        self.assertEqual(ContentRevision.query.count(), 6)

    def test_process_death_rolls_back_and_releases_the_import_lock(self):
        script = f'''
from unittest.mock import patch
from project import create_app
from project.learning.content_schema import load_catalog
from project.services import curriculum_service as service
with create_app({self.config!r}).app_context():
    checksum = service.content_checksum
    calls = 0
    def stop_during_import(item, schema_version):
        global calls
        calls += 1
        if calls == 2:
            print("READY", flush=True)
            input()
        return checksum(item, schema_version)
    with patch.object(service, "content_checksum", stop_during_import):
        service.import_catalog(load_catalog({str(CATALOG)!r}), dry_run=False)
'''
        child = subprocess.Popen([sys.executable, "-c", script], stdin=subprocess.PIPE,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            self.assertTrue(io_select.select([child.stdout], [], [], 15)[0])
            self.assertEqual(child.stdout.readline().strip(), "READY")
            self.assertEqual(CurriculumItem.query.count(), 0)
            self.assertEqual(ContentRevision.query.count(), 0)
        finally:
            child.terminate()
            child.communicate(timeout=10)
        self.assertEqual(service.import_catalog(self.catalog, dry_run=False)["inserted"], 6)

    # Alembic's CLI logging setup disables unrelated loggers in this test process.
    # Isolate only that setup; run the real migration environment and database DDL.
    @patch("logging.config.fileConfig")
    def test_alembic_upgrade_and_downgrade_preserve_existing_review_history(self, _logging_setup):
        user = User(id=1, username="fixture", email="fixture@example.test")
        db.session.add(user)
        db.session.commit()
        with tempfile.TemporaryDirectory() as directory:
            notes = Path(directory)
            (notes / "fixture.json").write_text(json.dumps(dict(id="fixture", title="Fixture",
                flashcards=[dict(id="q", question="Question", answer="Answer")])))
            rate_card_for_user(user=user, notes_dir=notes, card_id="fixture:q", rating=4,
                request_id=str(uuid4()), expected_revision=0)
        before = {model.__tablename__: [dict(row) for row in db.session.execute(
            model.__table__.select()).mappings()] for model in (ReviewProgress, ReviewLog, ReviewReceipt)}
        # Populated practice tables must downgrade cleanly without touching catalog or review rows.
        service.import_catalog(self.catalog, dry_run=False, **REVIEW)
        session_id = practice_service.start_session(user, exercise_id="idempotent-order-api",
                                                    request_id=str(uuid4()))["session_id"]
        practice_service.save_work(user, session_id, request_id=str(uuid4()), edits=[
            dict(artifact_id="api", base_revision=0, language="text", body="POST /orders")])
        # And AI replies: a failed reply, a retried one that completed, its charges, and a 'reply' receipt.
        self.app.config.update(LEARNING_AI_ENABLED=True, LEARNING_AI_PROVIDER="fake",
                               LEARNING_AI_OWNER_EMAIL="fixture@example.test")
        user.email_verified = True
        db.session.commit()
        practice_service.send_turn(user, session_id, body="Do keys expire?", expected_sequence=1,
                                   artifact_revisions={"api": 1, "schema": 0, "algorithm": 0}, brief_revision=0,
                                   request_id=str(uuid4()))
        with self.assertLogs("project", "WARNING"):
            practice_worker.run_once(practice_worker.FakeProvider("fail"))
        practice_service.request_reply(user, session_id, request_id=str(uuid4()))
        self.assertTrue(practice_worker.run_once(practice_worker.FakeProvider()))
        from tests.test_practice_submissions import submission_input
        submitted = practice_service.save_and_submit(user, session_id, **submission_input(
            practice_service.session_detail(user.id, session_id), '{}'))
        feedback_service.request_feedback(user, session_id, submitted["submission"]["sequence"], request_id=str(uuid4()))
        self.assertTrue(practice_worker.run_once(practice_worker.FakeProvider()))
        self.assertIsNotNone(feedback_service.detail(1, session_id, submitted["submission"]["sequence"])["feedback"])
        charge_count = db.session.execute(text("SELECT count(*) FROM learning_ai_charge")).scalar()
        db.session.remove()
        directory = str(ROOT / "migrations")
        stamp(directory=directory, revision="head")
        downgrade(directory=directory, revision="a0b1c2d3e4f5")
        with db.engine.connect() as connection:
            self.assertIsNone(connection.execute(text("SELECT to_regclass('practice_feedback')")).scalar())
            self.assertEqual(connection.execute(text("SELECT count(*) FROM ai_request WHERE kind = 'feedback'")).scalar(), 0)
            self.assertEqual(connection.execute(text("SELECT count(*) FROM practice_receipt WHERE operation = 'feedback'")).scalar(), 0)
            self.assertEqual(connection.execute(text("SELECT count(*) FROM learning_ai_charge")).scalar(), charge_count)
            self.assertEqual(connection.execute(text("SELECT count(*) FROM session_message WHERE kind = 'submission'")).scalar(), 1)
        upgrade(directory=directory, revision="head")
        self.assertIsNone(feedback_service.detail(1, session_id, submitted["submission"]["sequence"])["feedback"])
        db.session.remove()
        downgrade(directory=directory, revision="f9a0b1c2d3e4")
        with db.engine.connect() as connection:
            self.assertEqual(connection.execute(text("SELECT count(*) FROM practice_receipt WHERE operation = 'submit'")).scalar(), 0)
            self.assertEqual(connection.execute(text("SELECT count(*) FROM session_message WHERE kind = 'submission'")).scalar(), 1)
        upgrade(directory=directory, revision="head")
        self.assertEqual(practice_service.submission_detail(1, session_id, submitted["submission"]["sequence"])["submission"],
                         submitted["submission"])
        db.session.remove()
        downgrade(directory=directory, revision="d7e8f9a0b1c2")
        with db.engine.connect() as connection:
            for table in ("ai_request", "learning_ai_charge"):
                self.assertIsNone(connection.execute(text(f"SELECT to_regclass('{table}')")).scalar())
            self.assertEqual(connection.execute(text(
                "SELECT operation, count(*) FROM practice_receipt GROUP BY operation ORDER BY operation")).all(),
                [("save", 1), ("send", 1), ("start", 1)])
            # The conversation itself stays: the opening turn, the learner's turn, and the reply.
            self.assertEqual(connection.execute(text("SELECT count(*) FROM session_message")).scalar(), 4)
            self.assertIsNone(connection.execute(text(
                "SELECT 1 FROM information_schema.columns WHERE table_name = 'practice_session' "
                "AND column_name = 'profile_version'")).scalar())
        downgrade(directory=directory, revision="c6d7e8f9a0b1")
        with db.engine.connect() as connection:
            self.assertIsNone(connection.execute(text("SELECT to_regclass('practice_session')")).scalar())
            self.assertEqual(connection.execute(text("SELECT count(*) FROM content_revision")).scalar(), 6)
        downgrade(directory=directory, revision="a4b5c6d7e8f9")
        upgrade(directory=directory, revision="head")
        for model in (ReviewProgress, ReviewLog, ReviewReceipt):
            self.assertEqual([dict(row) for row in db.session.execute(model.__table__.select()).mappings()],
                             before[model.__tablename__])
        with db.engine.connect() as connection:
            changes = compare_metadata(MigrationContext.configure(connection), db.metadata)
            self.assertEqual(changes, [])
            # compare_metadata ignores CHECK constraints; verify the migrated ones directly.
            checks = dict(connection.execute(text(
                "SELECT conname, pg_get_constraintdef(oid) FROM pg_constraint WHERE contype = 'c' AND "
                "conrelid::regclass::text IN ('practice_session', 'artifact_revision', 'session_message', "
                "'practice_receipt', 'ai_request', 'learning_ai_charge')")).all())
            # compare_metadata doesn't compare partial-index predicates either.
            indexes = dict(connection.execute(text(
                "SELECT indexname, indexdef FROM pg_indexes WHERE tablename = 'ai_request'")).all())
        self.assertEqual(sorted(checks), sorted([
            "ck_practice_session_style", "ck_practice_session_status", "ck_artifact_revision_revision",
            "ck_artifact_revision_format", "ck_artifact_revision_language", "ck_session_message_sequence",
            "ck_session_message_role", "ck_session_message_kind", "ck_session_message_modality",
            "ck_practice_receipt_operation", "ck_ai_request_kind", "ck_ai_request_status", "ck_ai_request_context_from",
            "ck_learning_ai_charge_purpose", "ck_learning_ai_charge_state", "ck_learning_ai_charge_amounts"]))
        self.assertIn("'reply'", checks["ck_practice_receipt_operation"])
        self.assertIn("'submit'", checks["ck_practice_receipt_operation"])
        self.assertIn("'feedback'", checks["ck_practice_receipt_operation"])
        self.assertIn("WHERE", indexes["uq_ai_request_live"])
        self.assertIn("'pending'", indexes["uq_ai_request_live"])
        self.assertIn("'completed'", indexes["uq_ai_request_completed_turn"])
        for name, values in (("ck_artifact_revision_format", ARTIFACT_FORMATS),
                             ("ck_artifact_revision_language", ARTIFACT_LANGUAGES),
                             ("ck_practice_session_style", INTERACTION_STYLES)):
            for value in values:
                self.assertIn(f"'{value}'", checks[name])
        db.session.remove()
        downgrade(directory=directory, revision="a4b5c6d7e8f9")
        # The current ORM contains columns absent in this historical schema.
        with db.engine.connect() as connection:
            self.assertEqual(connection.execute(text("SELECT count(*) FROM review_log")).scalar(), 1)
        upgrade(directory=directory, revision="head")
