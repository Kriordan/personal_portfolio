import unittest
from unittest.mock import patch

from project import create_app
from project.database import db
from project.models import Job, User
from project.services import jobwizard_service


class JobwizardServiceTests(unittest.TestCase):
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

        with self.app.app_context():
            db.create_all()

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()

    def _login(self):
        with self.app.app_context():
            user = User(username="test", email="test@example.com")
            db.session.add(user)
            db.session.commit()
            user_id = user.id

        with self.client.session_transaction() as session:
            session["_user_id"] = str(user_id)
            session["_fresh"] = True

    def test_create_job_persists_and_renders_screenshot(self):
        with self.app.app_context():
            with patch.object(Job, "render_screenshot") as mock_render:
                job = jobwizard_service.create_job(
                    title="Engineer",
                    company_name="Acme",
                    listing_url="https://example.com/job",
                )

            mock_render.assert_called_once_with()
            self.assertIsNotNone(job.id)
            self.assertEqual(db.session.get(Job, job.id).title, "Engineer")

    def test_create_job_rejects_blank_fields(self):
        with self.app.app_context():
            with self.assertRaises(jobwizard_service.ValidationError):
                jobwizard_service.create_job(
                    title="  ",
                    company_name="Acme",
                    listing_url="https://example.com/job",
                )

    def test_get_job_raises_not_found_for_unknown_id(self):
        with self.app.app_context():
            with self.assertRaises(jobwizard_service.NotFoundError):
                jobwizard_service.get_job(999)

    def test_list_jobs_returns_all_jobs(self):
        with self.app.app_context():
            with patch.object(Job, "render_screenshot"):
                jobwizard_service.create_job(
                    title="Engineer",
                    company_name="Acme",
                    listing_url="https://example.com/a",
                )
                jobwizard_service.create_job(
                    title="Designer",
                    company_name="Globex",
                    listing_url="https://example.com/b",
                )

            jobs = jobwizard_service.list_jobs()
            self.assertEqual({job.title for job in jobs}, {"Engineer", "Designer"})

    def test_missing_job_returns_404_in_web_route(self):
        self._login()
        response = self.client.get("/jobwizard/999", base_url="https://localhost")
        self.assertEqual(response.status_code, 404)

    def test_create_job_web_route_delegates_to_service(self):
        self._login()
        with patch.object(Job, "render_screenshot"):
            response = self.client.post(
                "/jobwizard/add/",
                data={
                    "title": "Engineer",
                    "company_name": "Acme",
                    "listing_url": "https://example.com/job",
                },
                base_url="https://localhost",
            )

        self.assertEqual(response.status_code, 302)
        with self.app.app_context():
            jobs = jobwizard_service.list_jobs()
            self.assertEqual(len(jobs), 1)
            self.assertEqual(jobs[0].company_name, "Acme")
