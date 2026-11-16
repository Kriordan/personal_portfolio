"""Phone snapshot/evaluation contracts on PostgreSQL; all AI is deterministic and fake."""
from concurrent.futures import ThreadPoolExecutor
import json
from threading import Barrier
import unittest
from unittest.mock import patch
from uuid import uuid4

from sqlalchemy.exc import OperationalError

from project.database import db
from project.models import User
from project.services import feedback_service, practice_worker
from tests.feedback_fixtures import DISCOVERY, RACE, scripted_feedback
from tests import test_practice_mobile_build_postgres as build
from tests import test_practice_postgres as pg_base
from tests.test_practice_submissions import submission_input


@unittest.skipUnless(pg_base.URL, 'Set LIBRARY_TEST_POSTGRES_URL to the isolated local test database')
class MobileFeedbackPostgresTests(unittest.TestCase):
    start = build.MobileBuildPostgresTests.start
    count = build.MobileBuildPostgresTests.count
    tearDown = build.MobileBuildPostgresTests.tearDown
    call = build.MobileBuildPostgresTests.call
    artifact = build.MobileBuildPostgresTests.artifact

    def setUp(self):
        build.MobileBuildPostgresTests.setUp(self)
        self.app.config.update(LEARNING_AI_ENABLED=True, LEARNING_AI_PROVIDER='fake',
            LEARNING_AI_OWNER_EMAIL='practice1@example.test', LEARNING_AI_TOTAL_CAP_USD=5,
            LEARNING_AI_MONTHLY_CAP_USD=50)
        db.session.get(User, 1).email_verified = True
        db.session.commit()
        self.path = f'/sessions/{self.session_id}'
        self.call('PUT', self.path + '/artifacts/api', self.artifact(DISCOVERY + '\n' + RACE))

    def values(self):
        code, detail = self.call('GET', self.path)
        self.assertEqual(code, 200)
        return submission_input(detail)

    def snapshot(self):
        code, result = self.call('POST', self.path + '/submissions', self.values())
        self.assertEqual(code, 201)
        return result['submission']['sequence']

    def test_duplicate_phone_snapshots_commit_once_without_charging_or_changing_work(self):
        values, barrier = self.values(), Barrier(2)
        with ThreadPoolExecutor(2) as pool:
            pending = [pool.submit(self.call, 'POST', self.path + '/submissions', values, barrier=barrier)
                       for _ in range(2)]
            results = [p.result(timeout=20) for p in pending]
        self.assertEqual(results[0], results[1])
        self.assertEqual(results[0][0], 201)
        self.assertEqual(self.count('session_message', "kind = 'submission'"), 1)
        self.assertEqual(self.count('artifact_revision'), 1)
        self.assertEqual(self.count('learning_ai_charge'), 0)
        self.assertEqual(self.count('ai_request'), 0)
        receipt = self.call('GET', '/receipts/' + values['request_id'])[1]['receipt']
        self.assertEqual(receipt['operation'], 'submit')
        self.assertEqual(receipt['response'], results[0][1])

    def test_snapshot_racing_a_web_edit_preserves_the_original_view_or_rejects_it(self):
        values, barrier = self.values(), Barrier(2)
        with ThreadPoolExecutor(2) as pool:
            phone = pool.submit(self.call, 'POST', self.path + '/submissions', values, barrier=barrier)
            web = pool.submit(self.call, 'PUT', self.path + '/artifacts/api',
                              self.artifact('New web proposal', base=1), barrier=barrier)
            snapshot, saved = phone.result(timeout=20), web.result(timeout=20)
        self.assertEqual(saved[0], 200)
        self.assertIn(snapshot[0], (201, 409))
        if snapshot[0] == 201:
            self.assertEqual(snapshot[1]['submission']['checks'][0]['revision'], 1)
        else:
            self.assertIsNone(self.call('GET', '/receipts/' + values['request_id'])[1]['receipt'])
        self.assertEqual(self.call('GET', self.path)[1]['artifacts'][0]['body'], 'New web proposal')
        self.assertEqual(self.count('learning_ai_charge'), 0)

    def test_competing_feedback_requests_and_lost_response_share_one_request_and_charge(self):
        sequence = self.snapshot()
        path = f'{self.path}/submissions/{sequence}/feedback'
        values, barrier = {'request_id': str(uuid4())}, Barrier(2)
        with ThreadPoolExecutor(2) as pool:
            pending = [pool.submit(self.call, 'POST', path, values, barrier=barrier) for _ in range(2)]
            results = [p.result(timeout=20) for p in pending]
        self.assertEqual(results[0], results[1])
        self.assertEqual(results[0][0], 202)
        original = feedback_service.request_feedback
        def lost(*args, **kwargs):
            original(*args, **kwargs)
            raise OperationalError('', {}, Exception('fixture response lost after commit'))
        with patch.object(feedback_service, 'request_feedback', side_effect=lost):
            self.assertEqual(self.call('POST', path, values)[0], 503)
        receipt = self.call('GET', '/receipts/' + values['request_id'])[1]['receipt']
        self.assertEqual(receipt['response'], results[0][1])
        provider = practice_worker.FakeProvider(feedbacks=[scripted_feedback])
        self.assertTrue(practice_worker.run_once(provider))
        self.assertEqual(self.call('POST', path, {'request_id': str(uuid4())})[1]['request']['status'], 'completed')
        self.assertFalse(practice_worker.run_once(provider))
        self.assertEqual(len(provider.calls), 1)
        self.assertEqual(self.count('ai_request'), 1)
        self.assertEqual(self.count('learning_ai_charge', "state = 'settled'"), 1)
        self.assertEqual(self.count('practice_feedback'), 1)

    def test_pending_assessment_uses_immutable_artifacts_and_notes_while_phone_keeps_editing(self):
        self.call('PUT', self.path + '/brief', {'request_id': str(uuid4()), 'base_revision': 0,
            'entries': [dict(id='scope', type='decision', text=DISCOVERY, pinned=True)]})
        sequence = self.snapshot()
        path = f'{self.path}/submissions/{sequence}'
        self.assertEqual(self.call('POST', path + '/feedback', {'request_id': str(uuid4())})[0], 202)
        self.assertEqual(self.call('PUT', self.path + '/artifacts/api', self.artifact('NEWER ARTIFACT', base=1))[0], 200)
        self.assertEqual(self.call('PUT', self.path + '/brief', {'request_id': str(uuid4()), 'base_revision': 1,
            'entries': [dict(id='scope', type='decision', text='NEWER NOTE', pinned=True)]})[0], 200)
        self.assertEqual(self.call('POST', self.path + '/submissions', self.values())[0], 409)
        provider = practice_worker.FakeProvider(feedbacks=[scripted_feedback])
        self.assertTrue(practice_worker.run_once(provider))
        model_input = json.loads(provider.calls[0]['input'])
        self.assertNotIn('NEWER ARTIFACT', json.dumps(model_input))
        self.assertNotIn('NEWER NOTE', json.dumps(model_input))
        result = self.call('GET', path + '/feedback')[1]
        self.assertEqual(result['feedback']['findings'][1]['evidence'][0]['revision'], 1)
        saved = self.call('GET', path)[1]
        self.assertEqual(saved['session_brief']['entries'][0]['text'], DISCOVERY)
        for private in ('reference_reasoning', 'rubric', 'misconception_ids', 'hidden_constraints'):
            self.assertNotIn(private, json.dumps(result) + json.dumps(saved))
        self.assertEqual(self.count('review_log'), 0)

    def test_limits_before_and_after_queueing_never_make_an_unaffordable_call(self):
        sequence = self.snapshot()
        path = f'{self.path}/submissions/{sequence}/feedback'
        for settings, reason in [({'LEARNING_AI_TOTAL_CAP_USD': 0}, 'budget'),
                                 ({'LEARNING_AI_CONTEXT_BYTES': 100}, 'context_too_large')]:
            with patch.dict(self.app.config, settings):
                response = self.call('POST', path, {'request_id': str(uuid4())})
                self.assertEqual(response[1]['request']['reason'], reason)
        self.assertEqual(self.count('ai_request'), 0)
        self.assertEqual(self.call('POST', path, {'request_id': str(uuid4())})[0], 202)
        provider = practice_worker.FakeProvider(feedbacks=[scripted_feedback])
        with patch.dict(self.app.config, LEARNING_AI_TOTAL_CAP_USD=0):
            practice_worker.run_once(provider)
        self.assertEqual(provider.calls, [])
        self.assertEqual(self.count('learning_ai_charge'), 0)
        self.assertEqual(self.app.config['LEARNING_AI_TOTAL_CAP_USD'], 5)
        self.assertEqual(self.app.config['LEARNING_AI_MONTHLY_CAP_USD'], 50)
