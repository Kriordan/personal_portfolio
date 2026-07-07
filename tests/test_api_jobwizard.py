import unittest
from datetime import datetime, timezone
from unittest.mock import patch

from flask_jwt_extended import create_access_token

from project import create_app
from project.database import db
from project.models import Job, User


class ApiJobwizardTests(unittest.TestCase):
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

    def _create_user(self, *, email: str, username: str) -> int:
        with self.app.app_context():
            user = User(email=email, username=username, email_verified=True)
            user.set_password("password123")
            db.session.add(user)
            db.session.commit()
            return user.id

    def _create_job(
        self,
        *,
        user_id: int,
        title: str = "Engineer",
        company_name: str = "Acme",
        listing_url: str = "https://example.com/job",
    ) -> int:
        with self.app.app_context():
            job = Job(
                title=title,
                company_name=company_name,
                listing_url=listing_url,
                posted_date=datetime.now(timezone.utc),
                user_id=user_id,
            )
            db.session.add(job)
            db.session.commit()
            return job.id

    def _auth_headers(self, user_id: int) -> dict:
        with self.app.app_context():
            token = create_access_token(identity=str(user_id))
        return {"Authorization": f"Bearer {token}"}

    def _get(self, path: str, **kwargs):
        return self.client.get(path, base_url="https://localhost", **kwargs)

    def _post(self, path: str, **kwargs):
        return self.client.post(path, base_url="https://localhost", **kwargs)

    def test_jobwizard_endpoints_require_jwt(self):
        unauthenticated_requests = [
            self._get("/api/v1/jobwizard/jobs"),
            self._post(
                "/api/v1/jobwizard/jobs",
                json={
                    "title": "Engineer",
                    "company_name": "Acme",
                    "listing_url": "https://example.com/job",
                },
            ),
            self._get("/api/v1/jobwizard/jobs/1"),
        ]

        for response in unauthenticated_requests:
            self.assertEqual(response.status_code, 401)

    def test_get_jobs_returns_only_own_jobs(self):
        owner_id = self._create_user(email="owner@example.com", username="owner")
        other_id = self._create_user(email="other@example.com", username="other")
        own_job_id = self._create_job(user_id=owner_id, title="Engineer")
        self._create_job(user_id=other_id, title="Designer")

        response = self._get(
            "/api/v1/jobwizard/jobs", headers=self._auth_headers(owner_id)
        )

        self.assertEqual(response.status_code, 200)
        jobs = response.get_json()["jobs"]
        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0]["id"], own_job_id)
        self.assertEqual(jobs[0]["title"], "Engineer")

    def test_create_job_returns_serialized_payload(self):
        user_id = self._create_user(email="owner@example.com", username="owner")

        with patch.object(Job, "render_screenshot") as mock_render:
            response = self._post(
                "/api/v1/jobwizard/jobs",
                headers=self._auth_headers(user_id),
                json={
                    "title": "Engineer",
                    "company_name": "Acme",
                    "listing_url": "https://example.com/job",
                },
            )

        self.assertEqual(response.status_code, 201)
        mock_render.assert_called_once_with()
        job = response.get_json()["job"]
        for key in (
            "id",
            "title",
            "company_name",
            "listing_url",
            "listing_image",
            "posted_date",
            "user_id",
        ):
            self.assertIn(key, job)
        self.assertEqual(job["title"], "Engineer")
        self.assertEqual(job["company_name"], "Acme")
        self.assertEqual(job["listing_url"], "https://example.com/job")
        self.assertEqual(job["user_id"], user_id)

        with self.app.app_context():
            self.assertIsNotNone(db.session.get(Job, job["id"]))

    def test_create_job_validates_required_fields(self):
        user_id = self._create_user(email="owner@example.com", username="owner")

        response = self._post(
            "/api/v1/jobwizard/jobs",
            headers=self._auth_headers(user_id),
            json={"title": "  ", "company_name": "", "listing_url": ""},
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.get_json()["error"],
            "title, company_name, and listing_url are required",
        )

    def test_get_job_returns_owned_job(self):
        owner_id = self._create_user(email="owner@example.com", username="owner")
        job_id = self._create_job(user_id=owner_id)

        response = self._get(
            f"/api/v1/jobwizard/jobs/{job_id}", headers=self._auth_headers(owner_id)
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["job"]["id"], job_id)

    def test_get_job_returns_404_for_unknown_job(self):
        owner_id = self._create_user(email="owner@example.com", username="owner")

        response = self._get(
            "/api/v1/jobwizard/jobs/9999", headers=self._auth_headers(owner_id)
        )

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.get_json()["error"], "Job not found.")

    def test_get_job_hides_foreign_job_as_404(self):
        owner_id = self._create_user(email="owner@example.com", username="owner")
        intruder_id = self._create_user(
            email="intruder@example.com", username="intruder"
        )
        job_id = self._create_job(user_id=owner_id)

        response = self._get(
            f"/api/v1/jobwizard/jobs/{job_id}", headers=self._auth_headers(intruder_id)
        )

        self.assertEqual(response.status_code, 404)
