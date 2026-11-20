"""Phone response and focused-review recovery through JWT on real PostgreSQL."""
from concurrent.futures import ThreadPoolExecutor
import json
from threading import Barrier
import unittest
from unittest.mock import patch
from urllib.parse import urlencode
from uuid import uuid4

from flask_jwt_extended import create_access_token
from sqlalchemy.exc import OperationalError

from project.database import db
from project.models import LearningAICharge, PracticeFeedbackAnnotation, ReviewLog, ReviewProgress, User
from project.services import feedback_review_service as review
from tests import test_feedback_review_postgres as base


@unittest.skipUnless(base.URL, 'Set LIBRARY_TEST_POSTGRES_URL to the isolated local test database')
class MobileResponsePostgresTests(unittest.TestCase):
    tearDown = base.FeedbackReviewPostgresTests.tearDown

    def setUp(self):
        base.FeedbackReviewPostgresTests.setUp(self)
        self.app.config.update(LEARNING_PRACTICE_ENABLED=True,
            JWT_SECRET_KEY='mobile-response-fixture-secret-at-least-32-characters')
        self.token = create_access_token(identity='1')
        self.path = f'/api/v1/learning/practice/sessions/{self.sid}/submissions/{self.seq}/feedback/f2'
        self.charges = [(r.id, r.state, r.cost_microusd) for r in LearningAICharge.query.all()]
        db.session.remove()

    def call(self, method, path, payload=None, barrier=None):
        with self.app.test_client() as client:
            if barrier:
                barrier.wait(timeout=10)
            response = client.open(path, method=method, json=payload,
                headers={'Authorization': 'Bearer ' + self.token}, base_url='https://localhost')
            self.assertEqual(response.headers['Cache-Control'], 'private, no-store')
            return response.status_code, response.get_json()

    def response(self, **extra):
        return dict(request_id=str(uuid4()), expected_revision=0, decision='agree', note='Try simultaneous requests.', **extra)

    def assert_budget_unchanged(self):
        db.session.remove()
        self.assertEqual([(r.id, r.state, r.cost_microusd) for r in LearningAICharge.query.all()], self.charges)

    def test_jwt_concurrent_response_replays_are_one_revision_and_keep_notes_out_of_receipts(self):
        values = self.response()
        values['note'] = '💡' * 2000
        barrier = Barrier(2)
        with ThreadPoolExecutor(2) as pool:
            futures = [pool.submit(self.call, 'PUT', self.path + '/response', values, barrier) for _ in range(2)]
            results = [f.result(timeout=20) for f in futures]
        self.assertEqual(results[0], results[1])
        self.assertEqual(results[0][0], 200)
        receipt = self.call('GET', '/api/v1/learning/practice/receipts/' + values['request_id'])[1]['receipt']
        self.assertEqual(receipt['response'], results[0][1])
        self.assertNotIn('note', json.dumps(receipt))
        self.assertEqual(PracticeFeedbackAnnotation.query.one().revision, 1)
        self.assertEqual(ReviewLog.query.count(), 0)
        self.assert_budget_unchanged()

    def test_lost_response_replay_keeps_newer_web_note_and_exposes_explicit_conflict(self):
        values = self.response()
        original = review.annotate
        def lost(*args, **kwargs):
            original(*args, **kwargs)
            raise OperationalError('', {}, Exception('fixture lost response after commit'))
        with patch.object(review, 'annotate', side_effect=lost):
            self.assertEqual(self.call('PUT', self.path + '/response', values)[0], 503)
        with self.app.app_context():
            review.annotate(db.session.get(User, 1), self.sid, self.seq, 'f2', request_id=str(uuid4()),
                expected_revision=1, decision='disagree', note='Newer web response')
        replay = self.call('PUT', self.path + '/response', values)
        self.assertEqual((replay[0], replay[1]['revision']), (200, 1))
        fresh_id = dict(values, request_id=str(uuid4()), expected_revision=1)
        code, conflict = self.call('PUT', self.path + '/response', fresh_id)
        self.assertEqual((code, conflict['code']), (409, 'stale_annotation'))
        self.assertEqual(conflict['annotation']['note'], 'Newer web response')
        self.assertFalse(self.call('GET', self.path + '/review')[1]['accepted'])
        self.assertEqual(ReviewLog.query.count(), 0)
        self.assert_budget_unchanged()

    def test_lost_focused_rating_recovers_from_shared_receipt_after_disagreement_without_rescheduling(self):
        self.assertEqual(self.call('PUT', self.path + '/response', self.response())[0], 200)
        queue = self.call('GET', self.path + '/review')[1]
        card = queue['questions'][0]
        self.assertNotIn('answer', card)
        attempt = dict(request_id=str(uuid4()), card_id=card['card_id'], content_version=card['content_version'],
                       expected_revision=card['progress_revision'])
        answer = self.call('GET', self.path + '/review?' + urlencode(attempt))
        self.assertIn('answer', answer[1])
        self.assertEqual(ReviewLog.query.count(), 0)
        for private in ('misconception_ids', 'rubric', 'reference_reasoning'):
            self.assertNotIn(private, json.dumps([queue, answer]))
        values = dict(attempt, rating=0)
        original = review.rate_review
        def lost(*args, **kwargs):
            original(*args, **kwargs)
            raise OperationalError('', {}, Exception('fixture lost response after commit'))
        with patch.object(review, 'rate_review', side_effect=lost):
            self.assertEqual(self.call('POST', self.path + '/review', values)[0], 503)
        receipt = self.call('GET', '/api/v1/learning/ratings/' + attempt['request_id'])[1]['receipt']
        withdrawn = dict(self.response(), decision='disagree', expected_revision=1)
        self.assertEqual(self.call('PUT', self.path + '/response', withdrawn)[0], 200)
        self.assertEqual(self.call('POST', self.path + '/review', values), (200, receipt))
        self.assertEqual(self.call('POST', self.path + '/review', dict(values, request_id=str(uuid4())))[0], 409)
        remaining = self.call('GET', self.path + '/review')[1]
        self.assertEqual((remaining['accepted'], remaining['completed'], remaining['questions']), (False, 1, []))
        self.assertEqual(ReviewLog.query.count(), 1)
        self.assertEqual(ReviewProgress.query.one().revision, 1)
        self.assert_budget_unchanged()
