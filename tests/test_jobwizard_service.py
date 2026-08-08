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

    def _create_user(self, username="test", email="test@example.com"):
        with self.app.app_context():
            user = User(username=username, email=email)
            db.session.add(user)
            db.session.commit()
            return user.id

    def _login(self, user_id=None):
        if user_id is None:
            user_id = self._create_user()

        with self.client.session_transaction() as session:
            session["_user_id"] = str(user_id)
            session["_fresh"] = True
        return user_id

    def test_create_job_persists_and_renders_screenshot(self):
        user_id = self._create_user()
        with self.app.app_context():
            with patch.object(Job, "render_screenshot") as mock_render:
                job = jobwizard_service.create_job_for_user(
                    user_id=user_id,
                    title="Engineer",
                    company_name="Acme",
                    listing_url="https://example.com/job",
                )

            mock_render.assert_called_once_with()
            self.assertIsNotNone(job.id)
            persisted = db.session.get(Job, job.id)
            self.assertEqual(persisted.title, "Engineer")
            self.assertEqual(persisted.user_id, user_id)

    def test_create_job_rejects_blank_fields(self):
        user_id = self._create_user()
        with self.app.app_context():
            with self.assertRaises(jobwizard_service.ValidationError):
                jobwizard_service.create_job_for_user(
                    user_id=user_id,
                    title="  ",
                    company_name="Acme",
                    listing_url="https://example.com/job",
                )

    def test_get_job_raises_not_found_for_unknown_id(self):
        user_id = self._create_user()
        with self.app.app_context():
            with self.assertRaises(jobwizard_service.NotFoundError):
                jobwizard_service.get_job_for_user(user_id=user_id, job_id=999)

    def test_get_job_raises_not_found_for_foreign_user(self):
        owner_id = self._create_user()
        other_id = self._create_user(username="other", email="other@example.com")
        with self.app.app_context():
            with patch.object(Job, "render_screenshot"):
                job = jobwizard_service.create_job_for_user(
                    user_id=owner_id,
                    title="Engineer",
                    company_name="Acme",
                    listing_url="https://example.com/job",
                )

            with self.assertRaises(jobwizard_service.NotFoundError):
                jobwizard_service.get_job_for_user(user_id=other_id, job_id=job.id)

    def test_list_jobs_only_returns_own_jobs(self):
        owner_id = self._create_user()
        other_id = self._create_user(username="other", email="other@example.com")
        with self.app.app_context():
            with patch.object(Job, "render_screenshot"):
                jobwizard_service.create_job_for_user(
                    user_id=owner_id,
                    title="Engineer",
                    company_name="Acme",
                    listing_url="https://example.com/a",
                )
                jobwizard_service.create_job_for_user(
                    user_id=other_id,
                    title="Designer",
                    company_name="Globex",
                    listing_url="https://example.com/b",
                )

            jobs = jobwizard_service.list_jobs_for_user(owner_id)
            self.assertEqual({job.title for job in jobs}, {"Engineer"})

    def test_missing_job_returns_404_in_web_route(self):
        self._login()
        response = self.client.get("/jobwizard/999", base_url="https://localhost")
        self.assertEqual(response.status_code, 404)

    def test_foreign_job_returns_404_in_web_route(self):
        owner_id = self._create_user()
        with self.app.app_context():
            with patch.object(Job, "render_screenshot"):
                job = jobwizard_service.create_job_for_user(
                    user_id=owner_id,
                    title="Engineer",
                    company_name="Acme",
                    listing_url="https://example.com/job",
                )
                job_id = job.id

        other_id = self._create_user(username="other", email="other@example.com")
        self._login(user_id=other_id)
        response = self.client.get(
            f"/jobwizard/{job_id}", base_url="https://localhost"
        )
        self.assertEqual(response.status_code, 404)

    def test_home_only_shows_own_jobs(self):
        owner_id = self._create_user()
        other_id = self._create_user(username="other", email="other@example.com")
        with self.app.app_context():
            with patch.object(Job, "render_screenshot"):
                jobwizard_service.create_job_for_user(
                    user_id=owner_id,
                    title="OwnerJob",
                    company_name="Acme",
                    listing_url="https://example.com/a",
                )
                jobwizard_service.create_job_for_user(
                    user_id=other_id,
                    title="OtherJob",
                    company_name="Globex",
                    listing_url="https://example.com/b",
                )

        self._login(user_id=owner_id)
        response = self.client.get("/jobwizard", base_url="https://localhost")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"OwnerJob", response.data)
        self.assertNotIn(b"OtherJob", response.data)

    def test_create_job_web_route_delegates_to_service(self):
        user_id = self._login()
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
            jobs = jobwizard_service.list_jobs_for_user(user_id)
            self.assertEqual(len(jobs), 1)
            self.assertEqual(jobs[0].company_name, "Acme")
            self.assertEqual(jobs[0].user_id, user_id)
