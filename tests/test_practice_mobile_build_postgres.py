"""The phone's existing PUT/receipt contracts against real PostgreSQL, including races."""
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
import unittest
from uuid import uuid4

from flask_jwt_extended import create_access_token

from project.database import db
from project.models import User
from project.services import practice_service
from tests import test_practice_postgres as pg_base

BASE = '/api/v1/learning/practice'


@unittest.skipUnless(pg_base.URL, 'Set LIBRARY_TEST_POSTGRES_URL to the isolated local test database')
class MobileBuildPostgresTests(unittest.TestCase):
    start = pg_base.PracticePostgresTests.start
    count = pg_base.PracticePostgresTests.count
    tearDown = pg_base.PracticePostgresTests.tearDown

    def setUp(self):
        pg_base.PracticePostgresTests.setUp(self)
        self.app.config.update(LEARNING_PRACTICE_ENABLED=True,
                               JWT_SECRET_KEY='mobile-build-fixture-secret-at-least-32-characters')
        self.token = create_access_token(identity='1')

    def call(self, method, path, payload=None, *, barrier=None):
        with self.app.test_client() as client:
            if barrier:
                barrier.wait(timeout=10)
            response = client.open(BASE + path, method=method, json=payload,
                                   headers={'Authorization': 'Bearer ' + self.token}, base_url='https://localhost')
            return response.status_code, response.get_json()

    def artifact(self, body, base=0, request_id=None):
        return dict(request_id=request_id or str(uuid4()), base_revision=base, language='text', body=body)

    def assert_no_ai(self):
        self.assertEqual(self.count('ai_request'), 0)
        self.assertEqual(self.count('learning_ai_charge'), 0)

    def test_duplicate_phone_saves_commit_one_maximum_size_revision_and_one_receipt(self):
        payload = self.artifact('💡' * 16384)
        barrier = Barrier(2)
        path = f'/sessions/{self.session_id}/artifacts/api'
        with ThreadPoolExecutor(2) as pool:
            replies = [pool.submit(self.call, 'PUT', path, payload, barrier=barrier) for _ in range(2)]
            results = [reply.result(timeout=15) for reply in replies]
        self.assertEqual(results[0], results[1])
        self.assertEqual(results[0][0], 200)
        self.assertEqual(self.count('artifact_revision'), 1)
        self.assertEqual(self.count('practice_receipt', "operation = 'save'"), 1)
        code, receipt = self.call('GET', '/receipts/' + payload['request_id'])
        self.assertEqual((code, receipt['receipt']['operation']), (200, 'save'))
        self.assertEqual(receipt['receipt']['response'], results[0][1])
        code, detail = self.call('GET', f'/sessions/{self.session_id}')
        self.assertEqual(detail['artifacts'][0]['body'], payload['body'])
        self.assert_no_ai()

    def test_lost_phone_response_replayed_after_a_web_edit_keeps_the_newer_head(self):
        path = f'/sessions/{self.session_id}/artifacts/api'
        payload = self.artifact('phone proposal\r\nwith retries')
        original = self.call('PUT', path, payload)
        # The phone never receives this result. The web saves a newer revision meanwhile.
        practice_service.save_work(db.session.get(User, 1), self.session_id, request_id=str(uuid4()),
            edits=[dict(artifact_id='api', base_revision=1, language='text', body='newer web proposal')])
        self.assertEqual(self.call('PUT', path, payload), original)
        code, detail = self.call('GET', f'/sessions/{self.session_id}')
        self.assertEqual((detail['artifacts'][0]['revision'], detail['artifacts'][0]['body']), (2, 'newer web proposal'))
        code, version = self.call('GET', path + '/revisions/1')
        self.assertEqual(version['revision']['body'], 'phone proposal\nwith retries')
        rejected = self.call('PUT', path, self.artifact('phone keeps editing', base=1))
        self.assertEqual((rejected[0], rejected[1]['code']), (409, 'stale_artifact'))
        self.assertEqual(self.count('artifact_revision'), 2)
        self.assert_no_ai()

    def test_phone_and_web_notes_race_preserves_a_winner_and_requires_deliberate_reconciliation(self):
        path = f'/sessions/{self.session_id}/brief'
        self.call('PUT', f'/sessions/{self.session_id}/artifacts/api', self.artifact('saved evidence'))
        barrier = Barrier(2)
        source = [dict(artifact_id='api', revision=1)]

        def entry(label):
            return dict(id='decision-1', type='decision', text=label, pinned=True, basis='learner', sources=source)

        phone_id, web_id = str(uuid4()), str(uuid4())
        with ThreadPoolExecutor(2) as pool:
            phone = pool.submit(self.call, 'PUT', path,
                dict(request_id=phone_id, base_revision=0, entries=[entry('phone decision')]), barrier=barrier)

            def web_save():
                with self.app.app_context():
                    barrier.wait(timeout=10)
                    try:
                        return practice_service.save_work(db.session.get(User, 1), self.session_id,
                            request_id=web_id, brief=dict(base_revision=0, entries=[entry('web decision')]))
                    except practice_service.StaleViewError:
                        return 'stale'

            web = pool.submit(web_save)
            phone_result, web_result = phone.result(timeout=15), web.result(timeout=15)
        self.assertEqual((phone_result[0] == 409) + (web_result == 'stale'), 1)
        self.assertEqual(self.count('session_message', "kind = 'brief'"), 1)
        _, detail = self.call('GET', f'/sessions/{self.session_id}')
        self.assertEqual(detail['session_brief']['entries'][0]['sources'], source)
        self.assertTrue(detail['session_brief']['entries'][0]['pinned'])
        # Explicit comparison keeps both decisions, with the fresh base and a new request ID.
        merged = [entry('phone decision'), dict(entry('web decision'), id='decision-2')]
        reconciled = self.call('PUT', path, dict(request_id=str(uuid4()), base_revision=1, entries=merged))
        self.assertEqual((reconciled[0], reconciled[1]['brief']['revision']), (200, 2))
        _, detail = self.call('GET', f'/sessions/{self.session_id}')
        self.assertEqual(detail['session_brief']['entries'], merged)
        self.assert_no_ai()

    def test_save_racing_a_discussion_turn_never_cites_a_revision_the_learner_did_not_see(self):
        path = f'/sessions/{self.session_id}'
        self.call('PUT', path + '/artifacts/api', self.artifact('v1'))
        barrier = Barrier(2)
        with ThreadPoolExecutor(2) as pool:
            save = pool.submit(self.call, 'PUT', path + '/artifacts/api', self.artifact('v2', base=1), barrier=barrier)
            send = pool.submit(self.call, 'POST', path + '/turns', dict(request_id=str(uuid4()), body='My proposal',
                expected_sequence=1, artifact_revisions=dict(api=1, schema=0, algorithm=0), brief_revision=0), barrier=barrier)
            saved, sent = save.result(timeout=15), send.result(timeout=15)
        self.assertEqual(saved[0], 200)
        if sent[0] == 201:
            self.assertEqual(sent[1]['artifact_revisions'], [dict(artifact_id='api', revision=1)])
        else:
            self.assertEqual((sent[0], sent[1]['code']), (409, 'stale_artifact'))
        _, detail = self.call('GET', path)
        self.assertEqual(detail['artifacts'][0]['revision'], 2)
        self.assert_no_ai()
