"""Private attachments, ownership, and failure behavior for web and JWT exports."""
from unittest.mock import patch
from uuid import uuid4

from flask import g
from sqlalchemy.exc import OperationalError

from project.database import db
from project.models import User
from project.services import practice_export_service as exports, practice_service as practice
from tests.curriculum_v2_fixtures import PRIVATE_V2, publish_feedback_catalog
from tests.test_feedback_review import completed_feedback
from tests.test_feedback_routes import enable
from tests.test_practice_api import PracticeApiCase
from tests.test_practice_web import PracticeWebCase


class ExportFixture:
    def setUp(self):
        super().setUp()
        enable(self.app)
        publish_feedback_catalog()
        self.sid, self.seq, _ = completed_feedback(db.session.get(User, 1))

    def assert_attachment(self, response, format):
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["Content-Disposition"], f"attachment; filename=practice-{self.sid}.{format}")
        self.assertEqual(response.headers["Content-Type"], exports.FORMATS[format] + "; charset=utf-8")
        self.assertEqual(response.headers["Cache-Control"], "private, no-store")
        self.assertEqual(response.headers["X-Content-Type-Options"], "nosniff")
        self.assertEqual(int(response.headers["Content-Length"]), len(response.data))
        for secret in (*PRIVATE_V2, "misconception_ids", "reference_reasoning", "claim_token", "fixture1@example.test"):
            self.assertNotIn(secret, response.get_data(as_text=True))


class PracticeExportApiTests(ExportFixture, PracticeApiCase):
    def path(self, format="json", sid=None):
        return f"/sessions/{sid or self.sid}/export/{format}"

    def test_authenticated_json_and_markdown_downloads_are_private_attachments(self):
        for format in exports.FORMATS:
            response = self.call("GET", self.path(format))
            self.assert_attachment(response, format)
            if format == "json":
                self.assertEqual(response.get_json()["session"]["id"], self.sid)
                self.assertEqual(response.get_json()["schema_version"], 1)
        self.app.config["LEARNING_AI_ENABLED"] = False
        self.assert_attachment(self.call("GET", self.path()), "json")

    def test_authentication_ownership_formats_and_feature_flag(self):
        self.assertEqual(self.call("GET", self.path(), user_id=None).status_code, 401)
        self.assertEqual(self.call("GET", self.path(), user_id=2).status_code, 404)
        self.assertEqual(self.call("GET", self.path(sid=str(uuid4()))).status_code, 404)
        self.assertEqual(self.call("GET", self.path("html")).status_code, 400)
        self.assertEqual(self.call("POST", self.path(), {}).status_code, 405)
        with patch.dict(self.app.config, LEARNING_PRACTICE_ENABLED=False):
            self.assertEqual(self.call("GET", self.path()).status_code, 404)
        practice.delete_session(db.session.get(User, 1), self.sid)
        self.assertEqual(self.call("GET", self.path()).status_code, 404)

    def test_oversize_and_database_failure_never_masquerade_as_downloads(self):
        with patch.dict(self.app.config, LEARNING_EXPORT_MAX_BYTES=100):
            response = self.call("GET", self.path())
        self.assertEqual((response.status_code, response.get_json()["code"]), (413, "export_too_large"))
        self.assertNotIn("Content-Disposition", response.headers)
        with patch.object(exports, "_contents", side_effect=OperationalError("", {}, Exception("PRIVATE_DATABASE_TEXT"))):
            response = self.call("GET", self.path("md"))
        self.assertEqual(response.status_code, 503)
        self.assertNotIn("Content-Disposition", response.headers)
        self.assertNotIn("PRIVATE_DATABASE_TEXT", response.get_data(as_text=True))
        self.assert_attachment(self.call("GET", self.path()), "json")


class PracticeExportWebTests(ExportFixture, PracticeWebCase):
    def path(self, format="json"):
        return f"/learning/practice/{self.sid}/export/{format}"

    def test_downloads_and_workspace_delete_links_use_the_exact_session(self):
        for format in exports.FORMATS:
            self.assert_attachment(self.get(self.path(format)), format)
        practice.start_session(db.session.get(User, 1), exercise_id="idempotent-order-api", request_id=str(uuid4()))
        for path in (f"/learning/practice/{self.sid}", f"/learning/practice/{self.sid}/delete"):
            page = self.get(path).get_data(as_text=True)
            for format in exports.FORMATS:
                self.assertIn(self.path(format), page)
            self.assertIn('target="_blank" rel="noopener"', page)
            self.assertIn("Save your edits first", page)
            self.assertNotIn("Downloading a copy isn't available", page)

    def test_owner_login_feature_and_format_boundaries(self):
        self.assertEqual(self.get(self.path("html")).status_code, 400)
        self.assertEqual(self.post(self.path(), {}).status_code, 405)
        self.login(2)
        self.assertEqual(self.get(self.path()).status_code, 404)
        self.login(1)
        with patch.dict(self.app.config, LEARNING_PRACTICE_ENABLED=False):
            self.assertEqual(self.get(self.path()).status_code, 404)
        with self.client.session_transaction() as session:
            session.clear()
        g.pop("_login_user", None)
        self.assertEqual(self.get(self.path()).status_code, 302)

    def test_download_failures_use_a_standalone_safe_page_and_retry_is_read_only(self):
        with patch.object(exports, "_contents", side_effect=OperationalError("", {}, Exception("PRIVATE_DATABASE_TEXT"))), \
                patch.object(practice, "session_detail", side_effect=AssertionError("no second DB read")), \
                self.assertLogs(self.app.logger, level="WARNING") as log:
            response = self.get(self.path())
        self.assertEqual(response.status_code, 503)
        self.assertNotIn("Content-Disposition", response.headers)
        self.assertIn("Retry download", response.get_data(as_text=True))
        self.assertNotIn("PRIVATE_DATABASE_TEXT", response.get_data(as_text=True) + str(log.output))
        self.assertEqual(response.headers["Cache-Control"], "private, no-store")
        with patch.dict(self.app.config, LEARNING_EXPORT_MAX_BYTES=100):
            response = self.get(self.path())
        self.assertEqual(response.status_code, 413)
        self.assertNotIn("Content-Disposition", response.headers)
        self.assert_attachment(self.get(self.path()), "json")
