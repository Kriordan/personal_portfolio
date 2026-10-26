"""Verify outgoing Sentry envelopes with an in-memory transport, never the service."""
import json
import unittest
from unittest.mock import patch

from flask import Flask, abort, jsonify
import sentry_sdk
from sentry_sdk.transport import Transport
from project.monitoring import configure_monitoring, report_extraction_failure, scrub_event, valid_request_id

ID = "12345678-1234-1234-1234-123456789012"
SECRET = "PRIVATE_CANARY_9472"


class MemoryTransport(Transport):
    def __init__(self):
        super().__init__()
        self.events = []

    def capture_envelope(self, envelope):
        event = envelope.get_event()
        if event:
            self.events.append(event)


class MonitoringTests(unittest.TestCase):
    def tearDown(self):
        sentry_sdk.get_client().close()
        sentry_sdk.get_global_scope().set_client(None)

    def test_disabled_by_default_and_invalid_correlation_header_is_replaced(self):
        app = Flask(__name__)
        app.config.update(TESTING=True, SENTRY_ENABLED=False)
        with patch("sentry_sdk.init") as initialize:
            configure_monitoring(app)
        initialize.assert_not_called()
        response = app.test_client().get("/api/v1/missing", headers={"X-Request-ID": SECRET})
        self.assertTrue(valid_request_id(response.headers["X-Request-ID"]))
        self.assertNotEqual(response.headers["X-Request-ID"], SECRET)

    def test_automatic_flask_exception_is_scrubbed_before_transport(self):
        app, transport = self.enabled_app()
        @app.post("/api/v1/test-monitoring")
        def fail():
            private_local = SECRET
            raise ValueError(private_local)
        response = app.test_client().post("/api/v1/test-monitoring?token=" + SECRET,
            headers={"Authorization": "Bearer " + SECRET, "X-Request-ID": ID}, json={"notes": SECRET})
        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.headers["X-Request-ID"], ID)
        self.assertEqual(len(transport.events), 1)
        event = transport.events[0]
        self.assertNotIn(SECRET, json.dumps(event))
        self.assertNotIn("request", event)
        self.assertNotIn("server_name", event)
        self.assertEqual(event["tags"]["request_id"], ID)
        self.assertTrue(event["exception"]["values"][0]["stacktrace"]["frames"])

    def enabled_app(self):
        app = Flask(__name__)
        app.config.update(TESTING=True, PROPAGATE_EXCEPTIONS=False, SENTRY_ENABLED=True,
                          SENTRY_DSN="https://public@example.invalid/1", SENTRY_ENVIRONMENT="test")
        transport = MemoryTransport()
        configure_monitoring(app, transport=transport)
        self.assertTrue(app.extensions["error_reporting_enabled"])
        return app, transport

    def test_expected_failures_are_quiet_and_reporting_failure_cannot_escape(self):
        app, transport = self.enabled_app()
        with app.app_context():
            report_extraction_failure("read", "unsupported", attempt_id=ID)
            self.assertEqual(transport.events, [])
            report_extraction_failure("summary", "provider_auth", attempt_id=ID,
                                      exception=RuntimeError(SECRET))
            self.assertEqual(len(transport.events), 1)
            self.assertNotIn(SECRET, json.dumps(transport.events))
            with patch("sentry_sdk.capture_message", side_effect=RuntimeError("Transport failed")):
                report_extraction_failure("read", "invalid_request", attempt_id=ID)

    def test_expected_http_failures_do_not_emit_automatic_flask_events(self):
        app, transport = self.enabled_app()

        @app.get("/api/v1/expected/<int:status>")
        def expected(status):
            abort(status)

        @app.get("/api/v1/unsupported")
        def unsupported():
            report_extraction_failure("read", "unsupported", attempt_id=ID)
            return jsonify(code="unsupported", error=SECRET), 400

        @app.get("/api/v1/unavailable")
        def unavailable():
            report_extraction_failure("read", "unavailable", attempt_id=ID)
            return jsonify(code="unavailable", error=SECRET), 503

        client = app.test_client()
        for status in [401, 403, 404, 409, 410, 429]:
            with self.subTest(status=status):
                response = client.get(f"/api/v1/expected/{status}", headers={"X-Request-ID": ID})
                self.assertEqual(response.status_code, status)
                self.assertEqual(response.headers["X-Request-ID"], ID)
        self.assertEqual(client.get("/api/v1/unsupported").status_code, 400)
        self.assertEqual(client.get("/api/v1/unavailable").status_code, 503)
        self.assertEqual(transport.events, [])

    def test_transport_failure_preserves_api_result_and_request_correlation(self):
        app, transport = self.enabled_app()

        @app.post("/api/v1/provider-failed")
        def failed():
            report_extraction_failure("summary", "provider_auth", attempt_id=ID)
            return jsonify(code="provider_auth"), 502

        with patch.object(transport, "capture_envelope", side_effect=RuntimeError("Transport offline")):
            response = app.test_client().post("/api/v1/provider-failed", headers={"X-Request-ID": ID})
        self.assertEqual(response.status_code, 502)
        self.assertEqual(response.json, {"code": "provider_auth"})
        self.assertEqual(response.headers["X-Request-ID"], ID)

    def test_scrubber_drops_attachments_context_and_arbitrary_metadata(self):
        hint = {"attachments": [SECRET]}
        result = scrub_event(dict(message=SECRET, extra={"token": SECRET}, contexts={"job": SECRET},
            request={"data": SECRET}, breadcrumbs=[SECRET], user={"email": SECRET},
            tags={"request_id": SECRET, "code": SECRET}), hint)
        self.assertNotIn(SECRET, json.dumps(result))
        self.assertNotIn("attachments", hint)
