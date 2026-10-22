"""Saved-job correctness, receipts and capture failure paths; no live providers."""
import base64
import io
import json
import os
import signal
import subprocess
import sys
import time
import unittest
from datetime import datetime, timezone
from unittest.mock import Mock, patch
from uuid import uuid4
from urllib.parse import parse_qs, urlsplit

from PIL import Image
from project.database import db
from project.models import Job, JobCapture, JobMutationReceipt
from project.services import jobwizard_service as service, jobwizard_capture as capture
from project.jobwizard.capture_lock import capture_lock, capture_capacity
from project.jobwizard import capture_worker
from project.jobwizard.capture_policy import CaptureError, target_profile
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
        env = dict(JOBWIZARD_CAPTURE_ENABLED="1", BROWSERLESS_API_TOKEN="fixture", JOBWIZARD_PRIVATE_S3_BUCKET="fixture-private", AWS_ACCESS_KEY_ID="fixture", AWS_SECRET_ACCESS_KEY="fixture")
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

    def test_capacity_failure_is_receipted_and_requires_a_new_deliberate_attempt(self):
        self.setup_owner()
        job_id = self._create_job(user_id=self.owner)
        request_id = str(uuid4())
        with self.app.app_context(), patch.object(capture, "configured", return_value=True), patch.object(capture, "_run_capture") as provider:
            with capture_capacity() as first, capture_capacity() as second:
                self.assertIsNotNone(first); self.assertIsNotNone(second)
                result = capture.capture_job(user_id=self.owner, job_id=job_id, payload=dict(request_id=request_id, expected_revision=0))
                self.assertEqual(result["requested"]["error_code"], "capture_capacity")
                self.assertIn("slots", result["requested"]["error_message"])
            repeated = capture.capture_job(user_id=self.owner, job_id=job_id, payload=dict(request_id=request_id, expected_revision=0))
            self.assertEqual(repeated["requested"], result["requested"])
            provider.assert_not_called()

    def test_storage_or_provider_failure_has_a_safe_reason(self):
        self.setup_owner()
        job_id = self._create_job(user_id=self.owner)
        with self.app.app_context(), patch.object(capture, "configured", return_value=True):
            for failure, code in ((CaptureError("page_expired"), "page_expired"), (RuntimeError("S3 SECRET"), "capture_failed")):
                with patch.object(capture, "_run_capture", side_effect=failure):
                    result = capture.capture_job(user_id=self.owner, job_id=job_id, payload=dict(request_id=str(uuid4()), expected_revision=0))
                self.assertEqual(result["requested"]["error_code"], code)
                self.assertIsNone(result["image"])
                self.assertNotIn("SECRET", json.dumps(result))

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
        with self.app.app_context(), patch.dict(os.environ, dict(JOBWIZARD_CAPTURE_ENABLED="1", BROWSERLESS_API_TOKEN="fixture", JOBWIZARD_PRIVATE_S3_BUCKET="fixture-private", AWS_ACCESS_KEY_ID="fixture", AWS_SECRET_ACCESS_KEY="fixture")), patch.object(capture, "_run_capture", side_effect=artifact):
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
    def test_worker_accepts_unicode_url_within_the_service_limit(self):
        url = "https://example.com/?q=" + "界" * 1500
        self.assertTrue(service.safe_listing_url(url))
        payload = json.dumps(dict(url=url, key="j/" + "a" * 32 + ".png", parent_pid=os.getpid()))
        with patch.object(capture_worker.sys, "stdin", io.StringIO(payload)), patch.object(capture_worker.sys, "stdout", io.StringIO()), patch.object(capture_worker, "guard_worker"), patch.object(capture_worker, "capture_artifact", return_value={}) as provider:
            self.assertEqual(capture_worker.main(), 0)
            self.assertEqual(provider.call_args.args[0], url)

    def test_capture_requires_explicit_enablement_after_readiness_check(self):
        with patch.dict(os.environ, dict(BROWSERLESS_API_TOKEN="fixture", JOBWIZARD_PRIVATE_S3_BUCKET="fixture-private", JOBWIZARD_CAPTURE_ENABLED="0")):
            self.assertFalse(capture.configured())
            with patch.dict(os.environ, {"JOBWIZARD_CAPTURE_ENABLED": "1"}):
                self.assertTrue(capture.configured())

    def image(self):
        stream = io.BytesIO()
        metadata = Image.Exif()
        metadata[0x010E] = "Provider metadata must not be retained"
        Image.new("RGB", (20, 50), "blue").save(stream, "PNG", exif=metadata)
        return stream.getvalue()

    def test_provider_and_storage_are_validated_before_publishing(self):
        storage = Mock()
        storage.get_public_access_block.return_value = {"PublicAccessBlockConfiguration": dict.fromkeys(("BlockPublicAcls", "IgnorePublicAcls", "BlockPublicPolicy", "RestrictPublicBuckets"), True)}
        url = "https://job-boards.greenhouse.io/company/jobs/123"
        with patch.object(capture_worker, "validate_public_target"), patch.object(capture_worker, "s3_client", return_value=storage), patch.object(capture_worker, "browserless_image", return_value=self.image()) as provider:
            result = capture_worker.capture_artifact(url, "j/" + "a" * 32 + ".png")
            self.assertEqual(result["height"], 50)
            self.assertEqual(storage.put_object.call_args.kwargs["CacheControl"], "private, no-store")
            with Image.open(io.BytesIO(storage.put_object.call_args.kwargs["Body"])) as stored:
                self.assertEqual(stored.info, {})
            for data in (b"not an image", b"<html>Error</html>"):
                storage.put_object.reset_mock(); provider.return_value = data
                with self.assertRaises(Exception): capture_worker.capture_artifact(url, "j/" + "b" * 32 + ".png")
                storage.put_object.assert_not_called()
            provider.return_value = self.image()
            with patch.object(capture_worker, "MAX_PIXELS", 999):
                with self.assertRaises(CaptureError): capture_worker.capture_artifact(url, "j/" + "b" * 32 + ".png")
            storage.put_object.assert_not_called()
            provider.reset_mock()
            storage.get_public_access_block.return_value["PublicAccessBlockConfiguration"]["BlockPublicPolicy"] = False
            with self.assertRaises(ValueError): capture_worker.capture_artifact(url, "j/" + "b" * 32 + ".png")
            provider.assert_not_called()

    def test_transport_failures_and_size_limits_never_retry(self):
        response = Mock(status_code=200, headers={"Content-Type": "application/json; charset=UTF-8"})
        response.__enter__ = Mock(return_value=response); response.__exit__ = Mock(return_value=False)
        response.iter_content.return_value = [json.dumps({"type": "application/json", "data": {"image": base64.b64encode(self.image()).decode()}}).encode()]
        with patch.object(capture_worker.requests, "Session") as factory, patch.dict(os.environ, {"BROWSERLESS_API_TOKEN": "fixture"}):
            session = factory.return_value.__enter__.return_value
            session.post.return_value = response
            self.assertEqual(capture_worker.browserless_image("https://example.com", "ashby"), self.image())
            self.assertFalse(session.trust_env)
            self.assertFalse(session.post.call_args.kwargs["allow_redirects"])
            self.assertEqual(session.post.call_args.args[0], "https://production-sfo.browserless.io/function")
            for status, expected in ((401, "provider_auth"), (402, "provider_quota"), (429, "capture_capacity"), (408, "capture_timeout"), (504, "capture_timeout"), (500, "capture_failed"), (302, "capture_failed")):
                session.post.reset_mock(); response.status_code = status
                with self.assertRaises(CaptureError) as error: capture_worker.browserless_image("https://example.com", "ashby")
                self.assertEqual(error.exception.code, expected); self.assertEqual(session.post.call_count, 1)
            response.status_code = 200
            for payload in ({"type": "application/json", "data": {"error": "page_expired"}}, {"type": "application/json", "data": {"error": "SECRET"}}, [], {"image": "bad"}):
                response.iter_content.return_value = [json.dumps(payload).encode()]
                with self.assertRaises(CaptureError) as error: capture_worker.browserless_image("https://example.com", "ashby")
                self.assertNotIn("SECRET", str(error.exception))
            response.iter_content.return_value = [b"x" * 100]
            with patch.object(capture_worker, "MAX_RESPONSE_BYTES", 99):
                with self.assertRaises(CaptureError) as error: capture_worker.browserless_image("https://example.com", "ashby")
                self.assertEqual(error.exception.code, "image_too_large")
            session.post.side_effect = capture_worker.requests.Timeout("token-secret")
            with self.assertRaises(CaptureError) as error: capture_worker.browserless_image("https://example.com", "ashby")
            self.assertEqual(error.exception.code, "capture_timeout")

    def test_capture_target_scope_rejects_private_and_unverified_routes(self):
        valid = {
            "https://job-boards.greenhouse.io/acme/jobs/123?gh_src=public": "greenhouse",
            "https://jobs.eu.lever.co/acme/" + "a" * 36: "lever",
            "https://jobs.ashbyhq.com/acme/" + "b" * 36: "ashby",
            "https://acme.wd5.myworkdayjobs.com/Jobs/job/Role_123": "workday",
        }
        for url, profile in valid.items(): self.assertEqual(target_profile(url), profile)
        for url in ("https://127.0.0.1/job/a", "https://jobs.ashbyhq.com.evil.test/acme/" + "b" * 36, "http://job-boards.greenhouse.io/acme/jobs/123", "https://job-boards.greenhouse.io:444/acme/jobs/123", "https://job-boards.greenhouse.io/acme/jobs/123?token=secret", "https://job-boards.greenhouse.io/acme", "https://example.com/job"):
            self.assertIsNone(target_profile(url))
            with patch.object(capture_worker, "browserless_image") as provider:
                with self.assertRaises(CaptureError): capture_worker.capture_artifact(url, "j/" + "a" * 32 + ".png")
                provider.assert_not_called()

    def test_worker_only_returns_allowlisted_failure_codes(self):
        payload = json.dumps(dict(url="https://example.com", key="j/" + "a" * 32 + ".png", parent_pid=os.getpid()))
        for failure, expected in ((CaptureError("page_expired"), "page_expired"), (RuntimeError("SECRET"), "capture_failed")):
            output = io.StringIO()
            with patch.object(capture_worker.sys, "stdin", io.StringIO(payload)), patch.object(capture_worker.sys, "stdout", output), patch.object(capture_worker, "guard_worker"), patch.object(capture_worker, "capture_artifact", side_effect=failure):
                self.assertEqual(capture_worker.main(), 1)
            self.assertEqual(json.loads(output.getvalue()), {"error": expected})

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
        self.assertEqual(json.loads(run.call_args.kwargs["input"])["parent_pid"], os.getpid())

    @unittest.skipUnless(sys.platform == "linux", "Production parent-death signal requires Linux")
    def test_capture_child_stops_when_parent_dies(self):
        child_code = "from project.jobwizard.capture_worker import guard_worker; import os,sys,time; guard_worker(int(sys.argv[1])); print(os.getpid(),flush=True); time.sleep(90)"
        parent_code = f"import subprocess,sys,os,time; p=subprocess.Popen([sys.executable,'-c',{child_code!r},str(os.getpid())],stdout=subprocess.PIPE,text=True); print(p.stdout.readline().strip(),flush=True); time.sleep(90)"
        parent = subprocess.Popen([sys.executable, "-c", parent_code], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        child_pid = None
        try:
            import select
            self.assertTrue(select.select([parent.stdout], [], [], 15)[0])
            child_pid = int(parent.stdout.readline().strip())
            parent.terminate()
            parent.communicate(timeout=5)
            from pathlib import Path
            stat = Path(f"/proc/{child_pid}/stat")
            deadline = time.monotonic() + 3
            while stat.exists() and stat.read_text().split()[2] != "Z" and time.monotonic() < deadline:
                time.sleep(.05)
            self.assertTrue(not stat.exists() or stat.read_text().split()[2] == "Z")
        finally:
            if parent.poll() is None:
                parent.terminate()
            parent.communicate(timeout=5)
            if child_pid:
                try:
                    os.kill(child_pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
