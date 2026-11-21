import unittest

from flask import g

from project import create_app
from project.database import db
from project.models import User


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
        self.context = self.app.app_context()
        self.context.push()
        db.create_all()
        db.session.add(User(id=1, username="Learning fixture", email="learning@example.test"))
        db.session.commit()
        self.client = self.app.test_client()
        with self.client.session_transaction() as session:
            session["_user_id"] = "1"
            session["_fresh"] = True

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        db.engine.dispose()
        self.context.pop()

    def _get(self, path: str):
        return self.client.get(path, base_url="https://localhost")

    def test_learning_index_links_to_dedicated_destinations_after_login(self):
        navigation = self._get("/resume")
        self.assertEqual(navigation.status_code, 200)
        self.assertIn(b'href="/learning/">Learning</a>', navigation.data)
        response = self._get("/learning")

        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Engineering learning', response.data)
        self.assertIn(b'href="/learning/references"', response.data)
        self.assertIn(b'href="/learning/flashcards"', response.data)
        self.assertNotIn(b"Private study area", response.data)
        self.assertNotIn(b"data-learning-continue", response.data)

    def test_reference_catalog_preserves_the_article_link_after_login(self):
        response = self._get("/learning/references")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Web Performance", response.data)
        self.assertIn(
            b"/learning/web-performance/modern-images-video-lazy-loading-responsive-media",
            response.data,
        )

    def test_web_performance_reference_has_review_metadata_after_login(self):
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

    def test_every_learning_route_requires_login_before_reading_or_writing(self):
        with self.client.session_transaction() as session:
            session.clear()
        g.pop("_login_user", None)
        navigation = self._get("/resume")
        self.assertEqual(navigation.status_code, 200)
        self.assertNotIn(b'href="/learning/"', navigation.data)
        for rule in self.app.url_map.iter_rules():
            if not rule.endpoint.startswith("learning."):
                continue
            with self.app.test_request_context():
                from flask import url_for
                values = {name: 1 if name in ("revision", "sequence") else "fixture" for name in rule.arguments}
                path = url_for(rule.endpoint, **values)
            for method in rule.methods - {"OPTIONS"}:
                with self.subTest(path=path, method=method):
                    response = self.client.open(path, method=method, base_url="https://localhost")
                    self.assertEqual(response.status_code, 302)
                    self.assertIn("/login?next=", response.headers["Location"])
                    self.assertEqual(response.headers["Cache-Control"], "private, no-store")
                    self.assertNotIn(b"Modern Images", response.data)

    def test_review_done_link_is_generated_by_server_not_json_navigation(self):
        from flask import render_template, url_for

        # Render the real template with isolated adversarial card text. No
        # filesystem note mutation or authenticated production account.
        with self.app.test_request_context():
            html = render_template("learning/review.html", cards=[{
                "card_id": "fixture:1", "prompt": "</script><script>alert(1)</script>",
                "response": "javascript:alert(1)", "progress_revision": 0,
            }])
            expected = url_for("learning.flashcards")
        self.assertIn(f'id="review-summary-done" href="{expected}">Done</a>', html)
        self.assertNotIn('"doneUrl"', html)
        self.assertNotIn("</script><script>alert(1)</script>", html)


if __name__ == "__main__":
    unittest.main()
