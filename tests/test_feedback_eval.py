"""Review tooling safety and fixture plumbing; fake responses do not prove grading quality."""
import json
import os
import unittest

from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import DBAPIError

from project import create_app
from project.database import db
from project.learning import feedback_eval as review
from project.learning.content_schema import load_catalog
from project.models import LearningAICharge
from project.services.curriculum_service import import_catalog
from project.services.practice_worker import FakeProvider

URL = os.environ.get("LIBRARY_TEST_POSTGRES_URL")


class FeedbackEvaluationSafetyTests(unittest.TestCase):
    def test_cli_rejects_remote_application_and_non_postgres_databases(self):
        for url in ("sqlite://", "postgresql://localhost/portfolio", "postgresql://example.com/learning_feedback_eval",
                    "postgresql://localhost/learning_feedback_eval_fake"):
            with self.subTest(url=url), self.assertRaises(ValueError):
                review.guard_url(url, "openai")
        review.guard_url("postgresql://localhost/learning_feedback_eval", "openai")
        review.guard_url("postgresql://127.0.0.1/learning_feedback_eval_fake", "fake")


@unittest.skipUnless(URL, "Set LIBRARY_TEST_POSTGRES_URL to the isolated local test database")
class FeedbackEvaluationPostgresTests(unittest.TestCase):
    def setUp(self):
        parsed = make_url(URL)
        if parsed.host not in ("localhost", "127.0.0.1") or parsed.database != "library_sync_test":
            raise RuntimeError("Refusing fixtures outside the isolated local test database")
        self.app = create_app(dict(TESTING=True, SECRET_KEY="fixture", SQLALCHEMY_DATABASE_URI=URL,
            LEARNING_AI_ENABLED=True, LEARNING_AI_PROVIDER="fake", LEARNING_AI_OWNER_EMAIL=review.OWNER,
            LEARNING_AI_MONTHLY_CAP_USD=2))
        self.context = self.app.app_context()
        self.context.push()
        review.seed()
        self.document = review.load_cases()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        db.engine.dispose()
        self.context.pop()

    def run_case(self, provider, name="correct-transaction"):
        return review.run_case(self.document, next(c for c in self.document["cases"] if c["id"] == name), provider)

    def test_seeded_versions_match_the_real_importers_content_identity(self):
        for name in ("catalog.json", "catalog-v2.json"):
            catalog = load_catalog(review.ROOT / "curriculum/idempotency" / name)
            result = import_catalog(catalog, dry_run=True, publish=False)
            self.assertEqual(result["inserted"], 0)
            self.assertEqual(result["published"], 0)

    def test_fixtures_reach_real_snapshot_path_without_sending_answer_expectations(self):
        for case in self.document["cases"]:
            with self.subTest(case=case["id"]):
                provider = FakeProvider()
                result = review.run_case(self.document, case, provider)
                for key in ("completed_and_validated", "one_call", "assistance_coverage", "complete_snapshot"):
                    self.assertTrue(result["checks"][key], result)
                body = provider.calls[0]["input"]
                material = json.loads(body)
                self.assertNotIn("review_should", body)
                self.assertNotIn("expect_ids", body)
                for expectation in case["review"]:
                    self.assertNotIn(expectation, body)
                for artifact, content in {**self.document["bases"][case["base"]], **case.get("artifacts", {})}.items():
                    selected = next(a for a in material["artifacts"] if a["artifact_id"] == artifact and a["selected"])
                    self.assertEqual(selected["body"], content)
                revealed = {r["id"] for r in material["requirements"] if r["revealed"]}
                self.assertEqual(revealed, set(case["disclosures"]))
                if case.get("initial_artifacts"):
                    self.assertTrue(material["coverage"]["context_choices"])
                    self.assertIn(case["initial_message"], body)
                    self.assertTrue(any(not a["selected"] for a in material["artifacts"]))
                if case.get("notes"):
                    self.assertEqual(material["brief"]["entries"][0]["text"], case["notes"][0]["text"])
                if case.get("version") == 1:
                    self.assertNotIn("misconceptions", material["assessment"])
        self.assertEqual(LearningAICharge.query.count(), len(self.document["cases"]))
        self.assertTrue(all(row.state == "settled" for row in LearningAICharge.query.all()))

    def test_unknown_outcomes_keep_their_reservation_and_are_not_retried(self):
        provider = FakeProvider(mode="lost")
        result = self.run_case(provider)
        charge = LearningAICharge.query.one()
        self.assertEqual(len(provider.calls), 1)
        self.assertFalse(result["checks"]["completed_and_validated"])
        self.assertEqual(result["calls"][0]["charged"], "unknown")
        self.assertEqual(charge.state, "reserved")
        self.assertEqual(review.total_committed(), charge.reserved_microusd)

    def test_known_refusal_releases_cost_without_retry(self):
        provider = FakeProvider(mode="fail")
        result = self.run_case(provider)
        self.assertEqual(len(provider.calls), 1)
        self.assertEqual(result["calls"][0]["charged"], "no")
        self.assertEqual(LearningAICharge.query.one().state, "released")
        self.assertEqual(review.total_committed(), 0)

    def test_all_time_cap_counts_prior_month_unknown_charges_before_network(self):
        self.run_case(FakeProvider(mode="lost"))
        prior = LearningAICharge.query.one()
        prior.period = "2025-01"
        prior.reserved_microusd = review.CAP_MICROUSD - 1
        db.session.commit()
        provider = FakeProvider()
        result = self.run_case(provider)
        self.assertEqual(provider.calls, [])
        self.assertFalse(result["checks"]["one_call"])
        self.assertEqual(result["result"]["request"]["reason"], "evaluation_cap")
        self.assertEqual(review.total_committed(), review.CAP_MICROUSD - 1)
        self.assertEqual([c.state for c in LearningAICharge.query.order_by(LearningAICharge.id)], ["reserved", "released"])

    def test_postgres_lock_excludes_overlapping_review_processes(self):
        params = dict(a=review.LOCK[0], b=review.LOCK[1])
        acquire = text("SELECT pg_try_advisory_lock(:a, :b)")
        release = text("SELECT pg_advisory_unlock(:a, :b)")
        with db.engine.connect() as first, db.engine.connect() as second:
            self.assertTrue(first.execute(acquire, params).scalar())
            try:
                self.assertFalse(second.execute(acquire, params).scalar())
            finally:
                first.execute(release, params)
            self.assertTrue(second.execute(acquire, params).scalar())
            second.execute(release, params)

    def test_serializable_alternative_prevents_two_committed_absence_check_inserts(self):
        # Validate the critical premise of the alternative independently of the model.
        # No UNIQUE constraint exists on operation_key. Both writers read before either inserts.
        with db.engine.begin() as connection:
            connection.execute(text("CREATE TABLE feedback_ssi_probe (operation_key text, order_id integer)"))
        try:
            with db.engine.connect().execution_options(isolation_level="SERIALIZABLE") as first, \
                    db.engine.connect().execution_options(isolation_level="SERIALIZABLE") as second:
                query = text("SELECT order_id FROM feedback_ssi_probe WHERE operation_key = 'same'")
                self.assertEqual(first.execute(query).all(), [])
                self.assertEqual(second.execute(query).all(), [])
                first.execute(text("INSERT INTO feedback_ssi_probe VALUES ('same', 1)"))
                second.execute(text("INSERT INTO feedback_ssi_probe VALUES ('same', 2)"))
                first.commit()
                with self.assertRaises(DBAPIError) as error:
                    second.commit()
                self.assertEqual(error.exception.orig.sqlstate, "40001")
                second.rollback()
                # A whole-transaction retry reads the winner's receipt.
                self.assertEqual(second.execute(query).scalars().all(), [1])
        finally:
            with db.engine.begin() as connection:
                connection.execute(text("DROP TABLE feedback_ssi_probe"))
