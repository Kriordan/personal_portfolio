"""Saved-job correctness, receipts and capture failure paths; no live providers."""
import io
import json
import os
import unittest
from datetime import datetime, timezone
from unittest.mock import Mock, patch
from uuid import uuid4
from urllib.parse import parse_qs, urlsplit

from PIL import Image
from project.database import db
from project.models import Job, JobCapture, JobMutationReceipt
from project.services import jobwizard_service as service, jobwizard_capture as capture
from project.jobwizard.capture_lock import capture_lock
from project.jobwizard import capture_worker
from tests import test_api_jobwizard as baseline


class OrganizerTests(unittest.TestCase):
    setUp = baseline.ApiJobwizardTests.setUp
    tearDown = baseline.ApiJobwizardTests.tearDown
    _create_user = baseline.ApiJobwizardTests._create_user
    _create_job = baseline.ApiJobwizardTests._create_job
    _auth_headers = baseline.ApiJobwizardTests._auth_headers
    _post = baseline.ApiJobwizardTests._post
    _get = baseline.ApiJobwizardTests._get

    def setup_owner(self):
        self.owner = self._create_user(email="owner@example.test", username="owner")
        self.headers = self._auth_headers(self.owner)
        return self.owner

    def create(self, **extra):
        payload = dict(title="Engineer", company_name="Acme", listing_url="https://example.com/job", request_id=str(uuid4()))
        payload.update(extra)
        return self._post("/api/v1/jobwizard/jobs", headers=self.headers, json=payload), payload

    def update(self, job_id, **payload):
        return self.client.patch(f"/api/v1/jobwizard/jobs/{job_id}", base_url="https://localhost", headers=self.headers, json=payload)

    def test_strict_input_and_private_responses(self):
        self.setup_owner()
        for payload in ([], ["bad"], True, "bad", {"title": True}, {"title": "x" * 201, "company_name": "A", "listing_url": "https://example.com"}):
            response = self._post("/api/v1/jobwizard/jobs", headers=self.headers, json=payload)
            self.assertEqual(response.status_code, 400, payload)
            self.assertEqual(response.headers["Cache-Control"], "private, no-store")
        for url in ("javascript:alert(1)", "file:///a", "https://user:secret@example.com", "https://example.com\n", "https://example.com:bad", "https://example.com\\@private", "https://-bad.example", "https://example..com", "https://example.com:0"):
            # Trailing whitespace is normalized; embedded whitespace is rejected.
            if url.endswith("\n"):
                url = "https://exam\nple.com"
            self.assertEqual(self.create(listing_url=url)[0].status_code, 400)
        for method, path in (("get", "/api/v1/jobwizard/jobs"), ("get", "/api/v1/jobwizard/jobs/999")):
            response = getattr(self.client, method)(path, base_url="https://localhost", headers=self.headers)
            self.assertEqual(response.headers["Cache-Control"], "private, no-store")

    def test_create_receipt_replay_and_payload_mismatch(self):
        self.setup_owner()
        response, payload = self.create()
        self.assertEqual(response.status_code, 201)
        replay = self._post("/api/v1/jobwizard/jobs", headers=self.headers, json=payload)
        self.assertEqual(response.json, replay.json)
        mismatch = self._post("/api/v1/jobwizard/jobs", headers=self.headers, json={**payload, "title": "different"})
        self.assertEqual(mismatch.status_code, 409)
        self.assertEqual(self._get(f'/api/v1/jobwizard/receipts/{payload["request_id"]}', headers=self.headers).json["receipt"], response.json)
        with self.app.app_context():
            self.assertEqual(Job.query.count(), 1)
            self.assertEqual(JobMutationReceipt.query.count(), 1)
            self.assertIsNotNone(Job.query.one().saved_at)

    def test_removed_account_token_returns_private_json_401(self):
        self.setup_owner()
        from project.models import User
        with self.app.app_context():
            db.session.delete(db.session.get(User, self.owner))
            db.session.commit()
        response = self._get("/api/v1/jobwizard/jobs", headers=self.headers)
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json["code"], "unauthorized")
        self.assertEqual(response.headers["Cache-Control"], "private, no-store")

    def test_archive_restore_revision_and_receipt_before_revision(self):
        self.setup_owner()
        created, _ = self.create()
        job = created.json["job"]
        request_id = str(uuid4())
        archived = self.update(job["id"], request_id=request_id, expected_revision=0, archived=True)
        self.assertEqual(archived.status_code, 200)
        self.assertIsNotNone(archived.json["job"]["archived_at"])
        replay = self.update(job["id"], request_id=request_id, expected_revision=0, archived=True)
        self.assertEqual(archived.json, replay.json)
        stale = self.update(job["id"], request_id=str(uuid4()), expected_revision=0, title="Clobber")
        self.assertEqual(stale.status_code, 409)
        restored = self.update(job["id"], request_id=str(uuid4()), expected_revision=1, archived=False)
        self.assertIsNone(restored.json["job"]["archived_at"])
        self.assertEqual(restored.json["job"]["saved_at"], job["saved_at"])
        self.assertEqual(len(self._get("/api/v1/jobwizard/jobs", headers=self.headers).json["jobs"]), 1)

    def test_account_boundaries_for_mutation_status_and_images(self):
        self.setup_owner()
        created, payload = self.create()
        job_id = created.json["job"]["id"]
        other = self._create_user(email="other@example.test", username="other")
        self.headers = self._auth_headers(other)
        self.assertEqual(self.update(job_id, expected_revision=0, archived=True).status_code, 404)
        self.assertIsNone(self._get(f'/api/v1/jobwizard/receipts/{payload["request_id"]}', headers=self.headers).json["receipt"])
        self.assertEqual(self._get(f"/api/v1/jobwizard/jobs/{job_id}/capture", headers=self.headers).status_code, 404)
        self.assertEqual(self._post(f"/api/v1/jobwizard/jobs/{job_id}/capture", headers=self.headers, json=dict(request_id=str(uuid4()), expected_revision=0)).status_code, 404)

    def test_failed_commit_rolls_back_record_and_receipt(self):
        self.setup_owner()
        with self.app.app_context():
            with patch.object(db.session, "commit", side_effect=RuntimeError("stop")):
                with self.assertRaises(RuntimeError):
                    service.mutate_job(user_id=self.owner, payload=dict(title="Title", company_name="Company", listing_url="https://example.com", request_id=str(uuid4())))
            self.assertEqual(Job.query.count(), 0)
            self.assertEqual(JobMutationReceipt.query.count(), 0)

    def test_invalid_website_form_and_safe_legacy_link(self):
        self.setup_owner()
        with self.client.session_transaction() as session:
            session["_user_id"] = str(self.owner); session["_fresh"] = True
        response = self.client.post("/jobwizard/add/", base_url="https://localhost", data={"title": "Kept draft", "company_name": "", "listing_url": ""})
        self.assertEqual(response.status_code, 400)
        self.assertIn(b"Kept draft", response.data)
        self.assertIn(b'method="post"', response.data)
        job_id = self._create_job(user_id=self.owner, listing_url="javascript:alert(1)")
        response = self._get(f"/jobwizard/{job_id}")
        self.assertEqual(response.status_code, 200)
        self.assertNotIn(b'href="javascript:', response.data)
        self.assertIn(b"Date recorded", response.data)

    def test_optional_capture_replay_retains_previous_and_outdated(self):
        self.setup_owner()
        response, _ = self.create()
        job_id = response.json["job"]["id"]
        env = dict(APILEAP_ACCESS_KEY="fixture", JOBWIZARD_PRIVATE_S3_BUCKET="fixture-private", AWS_ACCESS_KEY_ID="fixture", AWS_SECRET_ACCESS_KEY="fixture")
        with self.app.app_context(), patch.dict(os.environ, env):
            request_id = str(uuid4())
            def artifact(url, key):
                return dict(object_key=key, width=100, height=900)
            with patch.object(capture, "_run_capture", side_effect=artifact) as provider:
                result = capture.capture_job(user_id=self.owner, job_id=job_id, payload=dict(request_id=request_id, expected_revision=0))
                repeated = capture.capture_job(user_id=self.owner, job_id=job_id, payload=dict(request_id=request_id, expected_revision=0))
            self.assertEqual(provider.call_count, 1)
            self.assertEqual(result["requested"]["status"], "succeeded")
            self.assertEqual(repeated["requested"]["id"], request_id)
            self.assertEqual(parse_qs(urlsplit(result["image"]["url"]).query)["X-Amz-Expires"], ["900"])
            self.assertEqual(Job.query.one().listing_image, "")
            service.mutate_job(user_id=self.owner, job_id=job_id, payload=dict(expected_revision=0, listing_url="https://example.com/changed"))
            with patch.object(capture, "_run_capture", side_effect=RuntimeError("credentials must not leak")):
                failed = capture.capture_job(user_id=self.owner, job_id=job_id, payload=dict(request_id=str(uuid4()), expected_revision=1))
            self.assertEqual(failed["latest"]["status"], "failed")
            self.assertTrue(failed["image"]["outdated"])
            self.assertNotIn("credentials", json.dumps(failed))

    def test_capture_status_recovers_only_abandoned_attempt(self):
        self.setup_owner()
        job_id = self._create_job(user_id=self.owner)
        with self.app.app_context():
            request_id = str(uuid4())
            db.session.add(JobCapture(id=request_id, job_id=job_id, user_id=self.owner, source_url="https://example.com", source_revision=0, status="running", started_at=datetime.now(timezone.utc)))
            db.session.commit()
            with capture_lock(job_id):
                self.assertEqual(capture.capture_status(user_id=self.owner, job_id=job_id)["latest"]["status"], "running")
            self.assertEqual(capture.capture_status(user_id=self.owner, job_id=job_id)["latest"]["status"], "interrupted")

    def test_competing_status_reads_do_not_claim_capture_is_running(self):
        self.setup_owner()
        job_id = self._create_job(user_id=self.owner)
        with self.app.app_context(), capture_lock(job_id):
            self.assertFalse(capture.capture_status(user_id=self.owner, job_id=job_id)["busy"])

    def test_url_changed_during_capture_marks_completed_snapshot_outdated(self):
        self.setup_owner()
        response, _ = self.create()
        job_id = response.json["job"]["id"]
        def artifact(url, key):
            service.mutate_job(user_id=self.owner, job_id=job_id,
                payload=dict(expected_revision=0, listing_url="https://example.com/new"))
            return dict(object_key=key, width=100, height=900)
        with self.app.app_context(), patch.dict(os.environ, dict(APILEAP_ACCESS_KEY="fixture", JOBWIZARD_PRIVATE_S3_BUCKET="fixture-private", AWS_ACCESS_KEY_ID="fixture", AWS_SECRET_ACCESS_KEY="fixture")), patch.object(capture, "_run_capture", side_effect=artifact):
            result = capture.capture_job(user_id=self.owner, job_id=job_id,
                payload=dict(request_id=str(uuid4()), expected_revision=0))
            self.assertEqual(result["latest"]["status"], "succeeded")
            self.assertTrue(result["image"]["outdated"])

    def test_unmodified_legacy_lengths_are_preserved_on_unrelated_edit(self):
        self.setup_owner()
        job_id = self._create_job(user_id=self.owner, title="x" * 240, listing_url="javascript:alert(1)")
        result = self.update(job_id, expected_revision=0, title="x" * 240,
                             company_name="Changed company", listing_url="javascript:alert(1)")
        self.assertEqual(result.status_code, 200)
        self.assertFalse(result.json["job"]["can_open_listing"])
        self.assertEqual(result.json["job"]["title"], "x" * 240)
        with self.client.session_transaction() as session:
            session["_user_id"] = str(self.owner)
            session["_fresh"] = True
        web = self.client.post(f"/jobwizard/{job_id}/edit", base_url="https://localhost", data={
            "title": "x" * 240, "company_name": "Website change", "listing_url": "javascript:alert(1)",
            "expected_revision": "1", "request_id": str(uuid4())})
        self.assertEqual(web.status_code, 302)


class CaptureProviderTests(unittest.TestCase):
    def image(self):
        stream = io.BytesIO(); Image.new("RGB", (20, 50), "blue").save(stream, "PNG"); return stream.getvalue()

    def test_provider_and_storage_are_validated_before_publishing(self):
        response = Mock(status_code=200, headers={"Content-Type": "image/png"})
        response.__enter__ = Mock(return_value=response); response.__exit__ = Mock(return_value=False)
        response.iter_content.return_value = [self.image()]
        storage = Mock()
        storage.get_public_access_block.return_value = {"PublicAccessBlockConfiguration": dict.fromkeys(("BlockPublicAcls", "IgnorePublicAcls", "BlockPublicPolicy", "RestrictPublicBuckets"), True)}
        with patch.object(capture_worker, "validate_public_target"), patch.object(capture_worker, "s3_client", return_value=storage), patch.object(capture_worker.requests, "get", return_value=response), patch.dict(os.environ, {"APILEAP_ACCESS_KEY": "fixture"}):
            result = capture_worker.capture_artifact("https://example.com", "j/" + "a" * 32 + ".png")
            self.assertEqual(result["height"], 50)
            self.assertEqual(storage.put_object.call_args.kwargs["CacheControl"], "private, no-store")
            for status, content, data in ((500, "image/png", self.image()), (200, "text/html", b"error"), (200, "image/png", b"not an image")):
                storage.put_object.reset_mock(); response.status_code = status; response.headers["Content-Type"] = content; response.iter_content.return_value = [data]
                with self.assertRaises(Exception): capture_worker.capture_artifact("https://example.com", "j/" + "b" * 32 + ".png")
                storage.put_object.assert_not_called()

    def test_private_targets_are_rejected_without_provider_calls(self):
        with patch.object(capture_worker.socket, "getaddrinfo", return_value=[(2, 1, 6, '', ('127.0.0.1', 80))]):
            for target in ("https://public.example.com", "http://127.0.0.1", "file:///etc/passwd", "https://user:secret@example.com", "http://metadata.google.internal"):
                with self.assertRaises(ValueError): capture_worker.validate_public_target(target)

    def test_parent_enforces_deadline_without_inheriting_dotenv(self):
        completed = Mock(returncode=0, stdout=json.dumps(dict(object_key="j/key.png", width=2, height=5)))
        with patch.object(capture.subprocess, "run", return_value=completed) as run:
            capture._run_capture("https://example.com", "j/key.png")
        self.assertEqual(run.call_args.kwargs["timeout"], 22)
        self.assertEqual(run.call_args.kwargs["env"]["PYTHON_DOTENV_DISABLED"], "1")
