"""Real PostgreSQL serialization at the new mobile adapter and existing web service."""
from concurrent.futures import ThreadPoolExecutor
import os
from threading import Barrier
import unittest
from uuid import uuid4

from flask_jwt_extended import create_access_token
from sqlalchemy.engine import make_url

from project import create_app
from project.database import db
from project.models import ReviewLog, ReviewProgress, ReviewReceipt, User
from project.services import learning_service
from tests.test_practice_service import seed_catalog

URL = os.environ.get('LIBRARY_TEST_POSTGRES_URL')


@unittest.skipUnless(URL, 'Set LIBRARY_TEST_POSTGRES_URL to the isolated PostgreSQL test database')
class ConceptApiPostgresTests(unittest.TestCase):
    def setUp(self):
        url = make_url(URL)
        if url.host not in {'127.0.0.1', 'localhost'} or url.database != 'library_sync_test':
            raise RuntimeError('Refusing fixtures outside the disposable database')
        self.app = create_app(dict(TESTING=True, SQLALCHEMY_DATABASE_URI=URL,
            SECRET_KEY='fixture-key-at-least-32-characters', JWT_SECRET_KEY='fixture-jwt-at-least-32-characters'))
        self.context = self.app.app_context()
        self.context.push()
        db.create_all()
        db.session.add(User(id=1, username='concept', email='concept@example.test'))
        db.session.commit()
        seed_catalog(self)

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        db.engine.dispose()
        self.context.pop()

    def race(self, ids):
        barrier = Barrier(2)
        def run(mobile, request_id):
            with self.app.app_context():
                user = db.session.get(User, 1)
                body = dict(card_id='idempotency:timeout', content_version=1, expected_revision=0,
                            request_id=request_id, rating=4)
                barrier.wait(timeout=10)
                if mobile:
                    result = self.app.test_client().post('/api/v1/learning/concepts/idempotency/rate',
                        json=body, base_url='https://localhost',
                        headers={'Authorization': 'Bearer ' + create_access_token(identity='1')})
                    return result.status_code, result.json
                try:
                    return 200, learning_service.rate_card_for_user(user=user,
                        notes_dir=learning_service.notes_dir_for_root(self.app.root_path), **body)
                except learning_service.ConflictError:
                    return 409, None
        with ThreadPoolExecutor(2) as pool:
            futures = [pool.submit(run, mobile, request_id) for mobile, request_id in zip((True, False), ids)]
            return [future.result(timeout=20) for future in futures]

    def test_web_and_phone_replay_one_request_without_duplicate_progress(self):
        request_id = str(uuid4())
        results = self.race([request_id, request_id])
        self.assertEqual(results[0], results[1])
        self.assertEqual(results[0][0], 200)
        self.assertEqual(ReviewLog.query.count(), 1)
        self.assertEqual(ReviewReceipt.query.count(), 1)
        self.assertEqual(ReviewProgress.query.one().revision, 1)

    def test_web_and_phone_competing_ratings_cannot_both_apply(self):
        results = self.race([str(uuid4()), str(uuid4())])
        self.assertEqual(sorted(status for status, _ in results), [200, 409])
        self.assertEqual(ReviewLog.query.count(), 1)
        self.assertEqual(ReviewLog.query.one().content_version, 1)
        self.assertEqual(ReviewProgress.query.one().revision, 1)
