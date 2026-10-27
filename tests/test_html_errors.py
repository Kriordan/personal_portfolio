"""Exercise the application's HTML error handlers through real requests."""

import unittest

from flask import abort
from werkzeug.datastructures import WWWAuthenticate
from werkzeug.exceptions import TooManyRequests, Unauthorized

from project import create_app


class HtmlErrorTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app(
            {
                "TESTING": True,
                "PROPAGATE_EXCEPTIONS": False,
                "SECRET_KEY": "test-secret",
                "JWT_SECRET_KEY": "test-jwt-secret-should-be-at-least-32",
                "SQLALCHEMY_DATABASE_URI": "sqlite://",
                "SQLALCHEMY_TRACK_MODIFICATIONS": False,
                "WTF_CSRF_ENABLED": False,
                "SENTRY_ENABLED": False,
            }
        )

        @self.app.get("/test-errors/<int:status>")
        def http_error(status):
            abort(status)

        @self.app.get("/test-errors/unexpected")
        def unexpected_error():
            raise RuntimeError("Private exception detail")

        @self.app.get("/test-errors/rate-limit")
        def rate_limit():
            raise TooManyRequests(retry_after=60)

        @self.app.get("/test-errors/authenticate")
        def authenticate():
            raise Unauthorized(www_authenticate=WWWAuthenticate("basic", {"realm": "test"}))

        self.client = self.app.test_client()

    def _get(self, path):
        return self.client.get(path, base_url="https://localhost")

    def test_registered_error_pages_return_their_http_status(self):
        for status in [401, 404, 429, 500]:
            with self.subTest(status=status):
                response = self._get(f"/test-errors/{status}")
                self.assertEqual(response.status_code, status)
                self.assertEqual(response.mimetype, "text/html")
                self.assertIn(f"<h1>{status}</h1>".encode(), response.data)

    def test_missing_route_returns_404_for_get_and_head(self):
        response = self._get("/nonexistent-page")
        self.assertEqual(response.status_code, 404)
        self.assertIn(b"<h1>404</h1>", response.data)

        response = self.client.head("/nonexistent-page", base_url="https://localhost")
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.data, b"")

    def test_unhandled_exception_returns_500_without_exception_details(self):
        with self.assertLogs(self.app.logger, level="ERROR"):
            response = self._get("/test-errors/unexpected")
        self.assertEqual(response.status_code, 500)
        self.assertIn(b"<h1>500</h1>", response.data)
        self.assertNotIn(b"Private exception detail", response.data)

    def test_rate_limit_preserves_retry_after(self):
        response = self._get("/test-errors/rate-limit")
        self.assertEqual(response.status_code, 429)
        self.assertEqual(response.headers["Retry-After"], "60")
        self.assertIn(b"<h1>429</h1>", response.data)

    def test_unauthorized_preserves_authentication_challenge(self):
        response = self._get("/test-errors/authenticate")
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.www_authenticate.type, "basic")
        self.assertEqual(response.www_authenticate.realm, "test")
        self.assertIn(b"<h1>401</h1>", response.data)

    def test_api_authentication_errors_remain_json(self):
        response = self._get("/api/v1/auth/me")
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.mimetype, "application/json")
        self.assertEqual(response.json, {"msg": "Missing Authorization Header"})


if __name__ == "__main__":
    unittest.main()
