import unittest

from project import create_app


class ApiFeatureRegistrationTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app(
            {
                "TESTING": True,
                "SECRET_KEY": "test-secret",
                "JWT_SECRET_KEY": "test-jwt-secret-should-be-at-least-32",
                "SQLALCHEMY_DATABASE_URI": "sqlite://",
                "SQLALCHEMY_TRACK_MODIFICATIONS": False,
                "WTF_CSRF_ENABLED": False,
            }
        )
        self.client = self.app.test_client()

    def _get(self, path: str):
        return self.client.get(path, base_url="https://localhost")

    def test_existing_feature_api_routes_are_registered_and_jwt_protected(self):
        protected_feature_routes = [
            "/api/v1/learning/notes",
            "/api/v1/wishlist/gifts",
            "/api/v1/library/playlists",
        ]

        for path in protected_feature_routes:
            with self.subTest(path=path):
                response = self._get(path)

                self.assertEqual(response.status_code, 401)
                self.assertNotEqual(response.status_code, 404)

