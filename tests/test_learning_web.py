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

    def test_review_done_link_is_generated_by_server_not_json_navigation(self):
        from flask import render_template, url_for

        # Render the real template with isolated adversarial card text. No
        # filesystem note mutation or authenticated production account.
        with self.app.test_request_context():
            html = render_template("learning/review.html", cards=[{
                "card_id": "fixture:1", "prompt": "</script><script>alert(1)</script>",
                "response": "javascript:alert(1)", "progress_revision": 0,
            }])
            expected = url_for("learning.index")
        self.assertIn(f'id="review-summary-done" href="{expected}">Done</a>', html)
        self.assertNotIn('"doneUrl"', html)
        self.assertNotIn("</script><script>alert(1)</script>", html)


if __name__ == "__main__":
    unittest.main()
