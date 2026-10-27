import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch
from flask_jwt_extended import create_access_token
from project import create_app
from project.database import db
from project.models import User
from project.lottery.models import LotterySnapshot, LotteryRefreshRun
from project.lottery.calculations import rank
from test_lottery import example

class LotteryApiTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app(dict(TESTING=True, SECRET_KEY='lottery-mobile', JWT_SECRET_KEY='lottery-mobile-test-secret-at-least-32', SQLALCHEMY_DATABASE_URI='sqlite://', WTF_CSRF_ENABLED=False))
        self.ctx = self.app.app_context(); self.ctx.push(); db.create_all()
        self.client = self.app.test_client()
        self.user = User(username='mobile', email='mobile@example.invalid', email_verified=True)
        db.session.add(self.user); db.session.commit()
        self.headers = {'Authorization': 'Bearer ' + create_access_token(identity=str(self.user.id))}
        now = datetime.now(timezone.utc)
        self.games = [dict(example('1', 20), source_at=now.isoformat(), url='https://ctlottery.com/games/scratch-games/1'), dict(example('2', 10), source_at=now.isoformat(), url='https://ctlottery.com/games/scratch-games/2')]
        self.games += [dict(self.games[0], game_number='3', status='ended'), dict(self.games[0], game_number='4', price=None, issue='Awaiting verified game details')]
        self.snapshot = LotterySnapshot(source='ct', source_at=now, fetched_at=now, digest='test', data={'games': self.games})
        db.session.add(self.snapshot); db.session.commit()
        db.session.add(LotteryRefreshRun(source='ct', started_at=now, finished_at=now, status='success', scheduled=True, snapshot_id=self.snapshot.id)); db.session.commit()

    def tearDown(self):
        db.session.remove(); db.drop_all(); self.ctx.pop()

    def get(self, path, headers=None):
        return self.client.get(path, base_url='https://localhost', headers=self.headers if headers is None else headers)

    def test_auth_private_and_deleted_user(self):
        for path in ['/api/v1/lottery/draws', '/api/v1/lottery/scratch-offs', '/api/v1/lottery/scratch-offs/ct/1']:
            self.assertEqual(self.get(path, {}).status_code, 401)
            self.assertEqual(self.get(path).headers['Cache-Control'], 'private, no-store')
        db.session.delete(self.user); db.session.commit()
        self.assertEqual(self.get('/api/v1/lottery/draws').status_code, 401)

    def test_rank_parity_filters_detail_and_no_upstream(self):
        with patch('requests.sessions.Session.request', side_effect=AssertionError('No upstream I/O')) as http:
            for target in (1000, 100000):
                for basis in ('ticket', 'dollar'):
                    data = self.get(f'/api/v1/lottery/scratch-offs?state=ct&target={target}&basis={basis}').json
                    expected = rank(self.games[:2], target, basis)
                    self.assertEqual([g['game_number'] for g in data['games']], [g['game_number'] for g in expected])
                    self.assertEqual(data['games'][0]['probability'], expected[0]['probability'])
                    self.assertEqual(len(data['pending']), 1)
                    self.assertEqual(data['status']['scheduled_status'], 'success')
            empty = self.get('/api/v1/lottery/scratch-offs?state=ct&prices_set=1').json
            self.assertEqual(empty['games'], [])
            self.assertEqual(self.get('/api/v1/lottery/scratch-offs?state=ct&q=2').json['games'][0]['game_number'], '2')
            self.assertEqual(self.get('/api/v1/lottery/scratch-offs/ct/3').json['game']['reason'], 'Game ended')
            self.assertEqual(self.get('/api/v1/lottery/scratch-offs/ct/4').json['game']['reason'], 'Awaiting verified game details')
            self.assertEqual(self.get('/api/v1/lottery/scratch-offs/ct/999').status_code, 404)
            self.assertEqual(self.get('/api/v1/lottery/scratch-offs/no/1').status_code, 404)
            self.assertEqual(self.get('/api/v1/lottery/draws?state=ct').json['plan']['state'], 'ct')
            http.assert_not_called()

    def test_last_valid_data_and_refresh_failure_visible(self):
        self.snapshot.source_at = datetime.now(timezone.utc) - timedelta(days=3)
        db.session.add(LotteryRefreshRun(source='ct', started_at=datetime.now(timezone.utc), status='failed', error='Source blocked'))
        db.session.commit()
        data = self.get('/api/v1/lottery/scratch-offs?state=ct').json
        self.assertTrue(data['status']['stale']); self.assertEqual(data['status']['failure'], 'Source blocked')
        self.assertEqual(len(data['games']), 2)

    def test_home_private_card_only_after_login_and_no_upstream(self):
        self.assertNotIn('LOTTERY QUICK REFERENCE', self.get('/').text)
        with self.client.session_transaction(base_url='https://localhost') as session:
            session['_user_id'] = str(self.user.id); session['_fresh'] = True
        from flask import g
        g.pop('_login_user', None)
        with patch('requests.sessions.Session.request', side_effect=AssertionError('No upstream I/O')):
            response = self.get('/?lottery_state=ct')
            self.assertEqual(response.status_code, 200)
            self.assertIn('One stop a week', response.text)
            self.assertIn('private, no-store', response.headers['Cache-Control'])
