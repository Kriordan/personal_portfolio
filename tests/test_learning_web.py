import unittest

from project import create_app


class LearningWebTests(unittest.TestCase):
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

    def test_learning_index_is_public_and_links_to_reference(self):
        response = self._get("/learning")

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Web Performance", response.data)
        self.assertIn(
            b"/learning/web-performance/modern-images-video-lazy-loading-responsive-media",
            response.data,
        )
        self.assertNotIn(b"Private study area", response.data)

    def test_web_performance_reference_is_public_and_has_review_metadata(self):
        response = self._get(
            "/learning/web-performance/modern-images-video-lazy-loading-responsive-media"
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn(
            b"Modern Images, Video, Lazy Loading &amp; Responsive Media",
            response.data,
        )
        self.assertIn(b"Last reviewed:</span> August 7, 2026", response.data)
        self.assertIn(b'<meta property="og:type" content="article"', response.data)


if __name__ == "__main__":
    unittest.main()
