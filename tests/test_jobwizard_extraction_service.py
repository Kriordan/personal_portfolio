"""Durable extraction lifecycle and atomic acceptance without paid providers."""
import copy
import unittest
from datetime import timedelta
from unittest.mock import patch
from uuid import uuid4

from project.database import db
from project.models import Job, JobExtraction
from project.services import jobwizard_extraction as extraction
from project.jobwizard.extraction import normalize_source, validate_summary
from project.jobwizard.extraction_errors import SuggestionError
from project.jobwizard.capture_lock import capture_lock, capture_capacity
from tests import test_jobwizard_organizer as organizer

URL = "https://job-boards.greenhouse.io/acme/jobs/123"
SOURCE = normalize_source(dict(final_url=URL, heading="Engineer", page_title="Job Application for Engineer at Acme",
    header_text="Acme Engineer", description="Build reliable software for our customers. This role is remote in the US only. No visa sponsorship is available. Work with Python and PostgreSQL on web services.", jsonld=[]), URL, "greenhouse")
RESULT = validate_summary({"bullets": [{"category": "responsibilities", "text": "Build reliable software for our customers.", "evidence": [next(b["id"] for b in SOURCE["blocks"] if b["kind"] == "visible_description")]}], "more_details": True, "conflicts": []}, SOURCE)


class ExtractionServiceTests(unittest.TestCase):
    _create_user = organizer.OrganizerTests._create_user
    _auth_headers = organizer.OrganizerTests._auth_headers
    _get = organizer.OrganizerTests._get
    _post = organizer.OrganizerTests._post
    setup_owner = organizer.OrganizerTests.setup_owner
    create = organizer.OrganizerTests.create
    update = organizer.OrganizerTests.update
    # Inherit the existing fixture setup, not a second database.
    def setUp(self):
        organizer.OrganizerTests.setUp(self)
        self.setup_owner()
        self.gate = patch.dict('os.environ', JOBWIZARD_EXTRACTION_ENABLED="1", BROWSERLESS_API_TOKEN="fixture", OPENAI_API_KEY="fixture")
        self.gate.start()
        self.calls = []
        def provider(stage, **payload):
            self.calls.append(stage)
            return copy.deepcopy(dict(source=SOURCE, seconds=1) if stage == "read" else dict(result=RESULT, model="fixture", usage={"total_tokens": 20}, seconds=1))
        self.provider = patch.object(extraction, "_run", side_effect=provider)
        self.mock = self.provider.start()

    def tearDown(self):
        self.provider.stop(); self.gate.stop(); organizer.OrganizerTests.tearDown(self)

    def start(self, **extra):
        payload = dict(request_id=str(uuid4()), listing_url=URL, **extra)
        return self._post('/api/v1/jobwizard/extractions', headers=self.headers, json=payload), payload

    def summary(self, attempt_id):
        return self._post(f'/api/v1/jobwizard/extractions/{attempt_id}/summary', headers=self.headers, json={})

    def status(self, attempt_id):
        return self._get(f'/api/v1/jobwizard/extractions/{attempt_id}', headers=self.headers)

    def review(self, attempt_id, text="Build reliable software for our customers."):
        return dict(extraction_id=attempt_id, bullets=[dict(index=0, text=text)])

    def test_two_stage_receipts_replay_and_atomic_save(self):
        read, payload = self.start(); self.assertEqual(read.status_code, 200)
        receipt = read.json['extraction']; aid = receipt['id']
        self.assertEqual(receipt['status'], 'ready'); self.assertNotIn('blocks', receipt)
        self.assertEqual(self._post('/api/v1/jobwizard/extractions', headers=self.headers, json=payload).json, read.json)
        summary = self.summary(aid); self.assertEqual(summary.json['extraction']['status'], 'complete')
        self.assertEqual(self.summary(aid).json, summary.json)
        self.assertEqual(self.status(aid).json, summary.json)
        self.assertEqual(self.calls, ['read', 'summary'])
        saved, write = self.create(listing_url=URL, reviewed_details=self.review(aid, 'My edited summary.'))
        self.assertEqual(saved.status_code, 201)
        details = saved.json['job']['accepted_details']
        self.assertTrue(details['bullets'][0]['edited']); self.assertTrue(details['bullets'][0]['evidence'])
        self.assertFalse(details['outdated'])
        self.assertEqual(self._post('/api/v1/jobwizard/jobs', headers=self.headers, json=write).json, saved.json)
        self.assertNotIn('accepted_details', self._get('/api/v1/jobwizard/jobs', headers=self.headers).json['jobs'][0])
        with self.app.app_context():
            attempt = db.session.get(JobExtraction, aid)
            self.assertIsNone(attempt.source); self.assertIsNone(attempt.result)
        changed = self.update(saved.json['job']['id'], expected_revision=0, listing_url='https://example.com/new')
        self.assertTrue(changed.json['job']['accepted_details']['outdated'])
        self.assertEqual(changed.json['job']['accepted_details']['bullets'], details['bullets'])

    def test_summary_failure_keeps_metadata_explicit_retry_reuses_source(self):
        read, payload = self.start(); aid = read.json['extraction']['id']
        self.mock.side_effect = SuggestionError('timeout')
        failed = self.summary(aid).json['extraction']
        self.assertEqual(failed['status'], 'failed'); self.assertTrue(failed['fields']['title'])
        before = self.mock.call_count
        self.summary(aid); self.status(aid)
        self.assertEqual(self.mock.call_count, before)
        retry, _ = self.start(retry_of=aid)
        self.assertEqual(retry.json['extraction']['status'], 'ready')
        self.assertEqual(self.mock.call_count, before)
        self.assertEqual(retry.json['extraction']['fetched_at'], read.json['extraction']['fetched_at'])
        saved, _ = self.create(listing_url=URL, reviewed_details=dict(extraction_id=aid, bullets=[]))
        self.assertEqual(saved.status_code, 201)

    def test_no_owner_crossing_url_reuse_or_forged_evidence(self):
        read, payload = self.start(); aid = read.json['extraction']['id']; self.summary(aid)
        other = self._create_user(email='second@example.test', username='second')
        headers = self.headers; self.headers = self._auth_headers(other)
        self.assertEqual(self.status(aid).status_code, 404)
        self.assertEqual(self.summary(aid).status_code, 404)
        self.assertEqual(self.create(listing_url=URL, reviewed_details=self.review(aid))[0].status_code, 404)
        self.assertEqual(self._post('/api/v1/jobwizard/extractions', headers=self.headers, json=payload).status_code, 409)
        self.headers = headers
        self.assertEqual(self.create(reviewed_details=self.review(aid))[0].status_code, 409)
        review = self.review(aid); review['bullets'][0]['evidence'] = ['invented']
        self.assertEqual(self.create(listing_url=URL, reviewed_details=review)[0].status_code, 400)
        with self.app.app_context(): self.assertEqual(Job.query.count(), 0)

    def test_revision_fence_preserves_existing_summary_and_receipt(self):
        saved, _ = self.create(listing_url=URL); jid = saved.json['job']['id']
        read, _ = self.start(job_id=jid, expected_revision=0); aid = read.json['extraction']['id']; self.summary(aid)
        self.update(jid, expected_revision=0, title='Newer')
        result = self.update(jid, expected_revision=1, reviewed_details=self.review(aid))
        self.assertEqual(result.status_code, 409)
        with self.app.app_context(): self.assertEqual(db.session.get(Job, jid).revision, 1)

    def test_expiry_denies_read_summary_accept_and_cli_prunes(self):
        read, _ = self.start(); aid = read.json['extraction']['id']
        with self.app.app_context():
            db.session.get(JobExtraction, aid).expires_at = extraction.now() - timedelta(seconds=1); db.session.commit()
        self.assertEqual(self.status(aid).status_code, 410)
        self.assertEqual(self.summary(aid).status_code, 410)
        self.assertEqual(self.create(listing_url=URL, reviewed_details=dict(extraction_id=aid, bullets=[]))[0].status_code, 410)
        result = self.app.test_cli_runner().invoke(args=['prune-job-extractions'])
        self.assertEqual(result.exit_code, 0); self.assertIn('Removed 1', result.output)

    def test_status_recovers_interruption_without_paid_work(self):
        read, _ = self.start(); aid = read.json['extraction']['id']
        with self.app.app_context():
            attempt = db.session.get(JobExtraction, aid); attempt.status = 'running'; attempt.stage = 'summary'; db.session.commit()
        self.assertEqual(self.status(aid).json['extraction']['status'], 'interrupted')
        self.assertEqual(self.calls, ['read'])

    def test_shared_capacity_and_account_busy_do_not_call_providers(self):
        with self.app.app_context(), capture_capacity() as a, capture_capacity() as b:
            self.assertTrue(a and b)
            read, _ = self.start()
            self.assertEqual(read.json['extraction']['error_code'], 'capacity')
        with self.app.app_context(), capture_lock(self.owner, extraction.ACCOUNT_NAMESPACE):
            self.assertEqual(self.start()[0].status_code, 429)
        self.assertEqual(self.calls, [])

    def test_limits_gate_and_error_sanitization(self):
        with patch.dict('os.environ', JOBWIZARD_EXTRACTION_ENABLED='0'):
            self.assertEqual(self.start()[0].status_code, 503)
            self.assertEqual(self.create()[0].status_code, 201)
        self.assertEqual(self.calls, [])
        self.mock.side_effect = RuntimeError('SECRET_TOKEN provider body')
        response, _ = self.start()
        self.assertEqual(response.json['extraction']['error_code'], 'failed')
        self.assertNotIn('SECRET_TOKEN', response.get_data(as_text=True))
        for _ in range(9): self.start()
        self.assertEqual(self.start()[0].status_code, 429)
