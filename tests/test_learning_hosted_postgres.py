"""Hosted release, cross-month accounting, and local cutover failure recovery on PostgreSQL."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import tempfile
from threading import Barrier
from unittest.mock import patch
from uuid import uuid4

from flask_migrate import upgrade
from sqlalchemy import select
from sqlalchemy.engine import make_url

from project import create_app
from project.database import db
from project.deployment import check_ready, release
from project.learning import hosted_pilot as hosted
from project.models import AIRequest, ContentRevision, LearningAICharge, PracticeSession, User
from project.services import concept_progress_service, curriculum_service, practice_budget, practice_service
from scripts import learning_hosted_handoff as handoff, learning_pilot as pilot, learning_pilot_storage as storage
from tests.hosted_pilot_fixtures import approval, config, environment
from tests.test_learning_hosted_migrations_postgres import DEPLOYED_REVISION, HostedPostgresCase, ROOT

NOW = datetime(2026, 11, 13, 12, tzinfo=timezone.utc)


def charge(*, user_id=1, state="settled", amount=250_000, period="2026-11"):
    return LearningAICharge(user_id=user_id, reply_id=str(uuid4()), purpose="reply", provider="openai",
        model="gpt-6.1-sol", service_tier="default", pricing_version=practice_budget.PRICING_VERSION,
        state=state, reserved_microusd=amount, cost_microusd=amount if state == "settled" else None,
        period=period, created_at=NOW - timedelta(days=10), expires_at=NOW - timedelta(days=9))


class HostedPilotPostgresTests(HostedPostgresCase):
    def local(self, directory):
        url, _ = self.target()
        try:
            settings = pilot.initialize(directory, database_url=url, email="learner@example.com", port=5068)
        finally:
            if (directory / pilot.SETTINGS).exists():
                original = storage.read_json(directory / pilot.SETTINGS)
                self.databases[-1] = (make_url(url), original["instance_id"])
        consent = pilot.authorize(directory, total_usd="5", verification_usd="1", allow_draft=True)
        return settings, consent

    def hosted_app(self, policy=None, *, mode="off"):
        url, identity = self.target()
        storage.create_database(url, identity)
        app = create_app(config(url, policy=policy, mode=mode))
        with app.app_context():
            upgrade(directory=str(ROOT / "migrations"), revision=DEPLOYED_REVISION)
            owner = User(id=app.config["LEARNING_HOSTED_OWNER_ID"], username="hosted-owner",
                         email=app.config["LEARNING_AI_OWNER_EMAIL"], email_verified=True)
            db.session.add(owner)
            db.session.commit()
        return app

    @patch("logging.config.fileConfig")
    def test_cutover_preserves_local_work_freezes_live_ai_and_carries_actual_uncertain_costs(self, _logging):
        with tempfile.TemporaryDirectory() as folder:
            directory = Path(folder) / "local"
            settings, consent = self.local(directory)
            with pilot.app_for(settings, approval=consent).app_context():
                concept_progress_service.enroll(1, "idempotency")
                user = db.session.get(User, 1)
                sid = practice_service.start_session(user, exercise_id="idempotent-order-api", request_id=str(uuid4()))["session_id"]
                practice_service.save_work(user, sid, request_id=str(uuid4()), status="paused",
                    edits=[dict(artifact_id="api", base_revision=0, language="text", body="Keep this local work")])
                db.session.add_all([charge(), charge(state="reserved", amount=500_000, period="2026-10"),
                                    charge(state="released", amount=1_000_000)])
                db.session.commit()
                before = practice_service.session_detail(1, sid)
                db.session.remove()
                db.engine.dispose()
            path = handoff.freeze(directory, owner_id=7, owner_email="owner@example.com")
            saved = hosted.validate_approval(storage.read_json(path))
            self.assertEqual(saved["carryover_microusd"], 750_000)
            self.assertEqual(saved["carryover_by_period"], {"2026-10": 500_000, "2026-11": 250_000})
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            self.assertEqual(handoff.freeze(directory, owner_id=7, owner_email="owner@example.com"), path)
            frozen = pilot.load_settings(directory)
            self.assertEqual(frozen["hosted_handoff_id"], saved["handoff_id"])
            for verification in (True, False):
                with self.assertRaises(storage.PilotError):
                    pilot.app_for(frozen, approval=consent, live=True, verification=verification)
            with self.assertRaises(storage.PilotError):
                pilot.authorize(directory, total_usd="5", verification_usd="1", allow_draft=True)
            with self.assertRaises(storage.PilotError):
                handoff.freeze(directory, owner_id=8, owner_email="owner@example.com")
            with pilot.app_for(frozen, approval=consent).app_context():
                self.assertEqual(practice_service.session_detail(1, sid), before)
                self.assertIsNotNone(concept_progress_service.progress(1, "idempotency")["enrolled_at"])
                self.assertEqual(practice_budget.committed(), 750_000)
                db.session.remove()
                db.engine.dispose()
            app = self.hosted_app(saved)
            with app.app_context():
                release()
                release()  # Config-only releases do not import twice or reset costs.
                self.assertEqual(PracticeSession.query.count(), 0)
                self.assertEqual(LearningAICharge.query.count(), 0)
                self.assertEqual(practice_budget.committed(), 750_000)
                self.assertEqual(ContentRevision.query.count(), 6)
                self.assertTrue(all(row.published_at is None and row.reviewed_by is None
                                    for row in ContentRevision.query.all()))
                exercise = curriculum_service.published_learner_item("idempotent-order-api")
                self.assertTrue(exercise["private_pilot_draft"])
                self.assertNotIn("assessment", exercise["content"])
                self.assertNotIn("facilitator", exercise["content"])
                with patch.dict(app.config, LEARNING_HOSTED_PILOT=False):
                    self.assertIsNone(curriculum_service.published_learner_item("idempotency"))
                db.session.remove()
                db.engine.dispose()

    @patch("logging.config.fileConfig")
    def test_interrupted_handoff_cannot_restart_paid_ai_and_retries_the_same_target(self, _logging):
        with tempfile.TemporaryDirectory() as folder:
            directory = Path(folder) / "local"
            original, consent = self.local(directory)
            write = storage.write_json
            def fail_portable_file(path, value):
                if Path(path).name == handoff.HANDOFF:
                    raise OSError("fixture disk failure")
                return write(path, value)
            with patch.object(storage, "write_json", side_effect=fail_portable_file), self.assertRaises(OSError):
                handoff.freeze(directory, owner_id=1, owner_email="owner@example.com")
            frozen = pilot.load_settings(directory)
            self.assertIn("hosted_handoff_id", frozen)
            self.assertFalse((directory / handoff.HANDOFF).exists())
            with self.assertRaises(storage.PilotError):
                pilot.app_for(frozen, approval=consent, live=True)
            with self.assertRaises(storage.PilotError):
                handoff.freeze(directory, owner_id=2, owner_email="other@example.com")
            completed = handoff.freeze(directory, owner_id=1, owner_email="owner@example.com")
            self.assertEqual(storage.read_json(completed)["handoff_id"], frozen["hosted_handoff_id"])
            self.assertEqual(frozen["secret_key"], original["secret_key"])
            with pilot.app_for(frozen, approval=consent).app_context():
                db.session.add(charge())
                db.session.commit()
                db.session.remove()
                db.engine.dispose()
            with self.assertRaises(storage.PilotError):
                handoff.freeze(directory, owner_id=1, owner_email="owner@example.com")

    @patch("logging.config.fileConfig")
    def test_handoff_requires_stopped_original_pilot_and_no_active_requests(self, _logging):
        with tempfile.TemporaryDirectory() as folder:
            directory = Path(folder) / "local"
            settings, consent = self.local(directory)
            with storage.operator_lock(directory), self.assertRaises(storage.PilotError):
                handoff.freeze(directory, owner_id=1, owner_email="owner@example.com")
            app = pilot.app_for(settings, approval=consent)
            app.config.update(LEARNING_AI_ENABLED=True, LEARNING_AI_PROVIDER="fake", LEARNING_AI_MODEL="fake-interviewer",
                              LEARNING_AI_SELECTOR_MODEL="fake-interviewer")
            with app.app_context():
                user = db.session.get(User, 1)
                sid = practice_service.start_session(user, exercise_id="idempotent-order-api", request_id=str(uuid4()))["session_id"]
                practice_service.send_turn(user, sid, request_id=str(uuid4()), body="Do keys expire?", expected_sequence=1,
                    artifact_revisions={"api": 0, "schema": 0, "algorithm": 0}, brief_revision=0)
                self.assertEqual(AIRequest.query.count(), 1)
                db.session.remove()
                db.engine.dispose()
            with self.assertRaises(storage.PilotError):
                handoff.freeze(directory, owner_id=1, owner_email="owner@example.com")
            self.assertNotIn("hosted_handoff_id", pilot.load_settings(directory))

    @patch("logging.config.fileConfig")
    def test_hosted_reservations_include_carried_costs_across_races_restarts_and_months(self, _logging):
        policy = approval(carryover_microusd=750_000, carryover_by_period={"2026-10": 500_000, "2026-11": 250_000})
        app = self.hosted_app(policy)
        with app.app_context():
            release()
        app.config.update(hosted.settings(environment(policy, mode="verification")))
        barrier = Barrier(2)
        def reserve():
            with app.app_context():
                barrier.wait(timeout=5)
                try:
                    practice_budget.reserve(user_id=1, reply_id=str(uuid4()), purpose="reply", provider="openai",
                        model="gpt-6.1-sol", tier="default", input_bytes=0, max_output_tokens=15_000,
                        expires_at=NOW + timedelta(seconds=60), now=NOW)
                    db.session.commit()
                    return "reserved"
                except practice_budget.BudgetExhausted:
                    db.session.rollback()
                    return "blocked"
                finally:
                    db.session.remove()
        with ThreadPoolExecutor(max_workers=2) as pool:
            self.assertCountEqual(list(pool.map(lambda _: reserve(), range(2))), ["reserved", "blocked"])
        for _ in range(2):
            restarted = create_app(config(app.config["SQLALCHEMY_DATABASE_URI"], policy=policy, mode="verification"))
            with restarted.app_context():
                self.assertEqual(practice_budget.committed(), 900_000)
                self.assertEqual(practice_budget.committed("2026-11"), 400_000)
                future = NOW + timedelta(days=40)
                self.assertFalse(practice_budget.fits(100_001, future))
                self.assertEqual(practice_budget.month_status(future)["total"]["spent_microusd"], 900_000)
                self.assertEqual(LearningAICharge.query.count(), 1)  # An expired uncertain reservation still counts.
                db.session.remove()
                db.engine.dispose()
        with app.app_context():
            app.config.update(hosted.settings(environment(policy, mode="pilot")))
            self.assertEqual(practice_budget.total_cap_microusd(), 5_000_000)
            db.session.add(charge(amount=4_100_000))
            db.session.commit()
            self.assertFalse(practice_budget.fits(1, NOW))
            db.session.remove()
            db.engine.dispose()

    @patch("logging.config.fileConfig")
    def test_readiness_rejects_missing_drafts_changed_owner_and_missing_dedicated_key(self, _logging):
        app = self.hosted_app()
        with app.app_context():
            upgrade(directory=str(ROOT / "migrations"))
            with self.assertRaisesRegex(RuntimeError, "draft packet"):
                check_ready()
            release()
            app.config.update(hosted.settings(environment(mode="pilot")))
            with patch.dict("os.environ", {"OPENAI_API_KEY": "unrelated"}, clear=True):
                with self.assertRaisesRegex(RuntimeError, "dedicated"):
                    check_ready()
            with patch.dict("os.environ", {"LEARNING_OPENAI_API_KEY": "fixture-no-provider-call"}):
                check_ready()
            app.config.update(hosted.settings(environment()))
            db.session.get(User, 1).email_verified = False
            db.session.commit()
            with self.assertRaisesRegex(RuntimeError, "owner"):
                check_ready()
            db.engine.dispose()
