"""Mobile lesson/review projections share web scheduling and owner-scoped receipts."""
from copy import deepcopy
from unittest.mock import patch
from urllib.parse import urlencode
from uuid import uuid4

from flask_jwt_extended import create_access_token
from sqlalchemy.exc import OperationalError

from project.database import db
from project.models import ContentRevision, ReviewLog, ReviewProgress, ReviewReceipt, UserConceptProgress
from project.services import concept_progress_service, learning_service
from tests.test_practice_service import PracticeServiceCase, SENTINELS, publish

BASE = '/api/v1/learning/concepts'
CONCEPT = BASE + '/idempotency'


class ConceptApiTests(PracticeServiceCase):
    def setUp(self):
        super().setUp()
        self.app.config['JWT_SECRET_KEY'] = 'concept-fixture-jwt-key-at-least-32-characters'
        self.client = self.app.test_client()

    def call(self, method, path, payload=None, user=1):
        return self.client.open(path, method=method, json=payload, base_url='https://localhost',
            headers={'Authorization': 'Bearer ' + create_access_token(identity=str(user))})

    def rate_input(self, **changes):
        return dict(card_id='idempotency:timeout', content_version=1, rating=4,
                    expected_revision=0, request_id=str(uuid4()), **changes)

    def test_browsing_is_read_only_and_answers_require_explicit_reveal(self):
        listing = self.call('GET', BASE)
        self.assertEqual(listing.status_code, 200)
        self.assertIsNone(listing.json['concepts'][0]['progress'])
        self.assertEqual(listing.json['concepts'][0]['due_count'], 0)
        detail = self.call('GET', CONCEPT)
        self.assertEqual(len(detail.json['concept']['content']['sections']), 3)
        self.assertEqual(self.call('GET', CONCEPT + '/review').json['cards'], [])
        self.call('POST', CONCEPT + '/enrollment', {})
        cards = self.call('GET', CONCEPT + '/review').json['cards']
        self.assertEqual(len(cards), 4)
        self.assertTrue(all('answer' not in c and 'explanation' not in c for c in cards))
        query = urlencode(dict(card_id=cards[0]['card_id'], content_version=1, expected_revision=0))
        for _ in range(2):
            answer = self.call('GET', CONCEPT + '/review/reveal?' + query)
            self.assertEqual(answer.status_code, 200)
            self.assertIn('answer', answer.json['card'])
        self.assertEqual(ReviewLog.query.count(), 0)
        self.assertEqual(ReviewReceipt.query.count(), 0)
        for response in (listing, detail, answer):
            self.assertEqual(response.headers['Cache-Control'], 'private, no-store')
            for secret in SENTINELS:
                self.assertNotIn(secret, response.get_data(as_text=True))

    def test_mobile_rating_and_web_share_one_receipt_and_progress_revision(self):
        self.call('POST', CONCEPT + '/enrollment', {})
        body = self.rate_input(response_ms=2500, session_id='phone-review')
        first = self.call('POST', CONCEPT + '/rate', body)
        self.assertEqual(first.status_code, 200)
        self.assertEqual(first.json['content_version'], 1)
        self.assertEqual(first.json, self.call('POST', CONCEPT + '/rate', body).json)
        same = learning_service.rate_card_for_user(user=self.user,
            notes_dir=learning_service.notes_dir_for_root(self.app.root_path), **body)
        self.assertEqual(first.json, same)
        receipt = self.call('GET', '/api/v1/learning/ratings/' + body['request_id'])
        self.assertEqual(receipt.json['receipt'], first.json)
        saved_payload = ReviewReceipt.query.one().payload
        self.assertEqual((saved_payload['response_ms'], saved_payload['session_id']), (2500, 'phone-review'))
        self.assertIsNone(self.call('GET', '/api/v1/learning/ratings/' + body['request_id'], user=2).json['receipt'])
        self.assertEqual(ReviewLog.query.count(), 1)
        self.assertEqual(ReviewProgress.query.one().revision, 1)
        self.assertEqual(self.call('POST', CONCEPT + '/rate', dict(body, request_id=str(uuid4()))).status_code, 409)
        self.assertEqual(self.call('POST', CONCEPT + '/rate', dict(body, rating=3)).status_code, 409)
        self.assertEqual(self.call('GET', CONCEPT + '/review/reveal?' + urlencode({
            'card_id': body['card_id'], 'content_version': 1, 'expected_revision': 0})).status_code, 409)
        self.assertEqual(self.call('GET', CONCEPT).json['due_count'], 3)

    def test_rating_keeps_server_arguments_out_of_the_request_contract(self):
        body = self.rate_input(response_ms=125, session_id='practice')
        with patch.object(learning_service, 'rate_card_for_user', return_value={'saved': True}) as rate:
            for field in ('notes_dir', 'user', 'now'):
                with self.subTest(field=field):
                    response = self.call('POST', CONCEPT + '/rate', {**body, field: 'fixture'})
                    self.assertEqual(response.status_code, 400)
            rate.assert_not_called()
            self.assertEqual(self.call('POST', CONCEPT + '/rate', body).status_code, 200)
        rate.assert_called_once_with(user=self.user, notes_dir=learning_service.notes_dir_for_root(self.app.root_path),
                                     **body)

    def test_explicit_revision_remains_pinned_after_a_new_publication(self):
        item = deepcopy(self.catalog['items'][1])
        item['version'] = 2
        item['content']['answer'] = 'Different revised answer'
        publish(item)
        db.session.commit()
        old = self.call('GET', CONCEPT + '/review/reveal?' + urlencode(dict(
            card_id=item['id'], content_version=1, expected_revision=0)))
        self.assertNotEqual(old.json['card']['answer'], item['content']['answer'])
        result = self.call('POST', CONCEPT + '/rate', self.rate_input())
        self.assertEqual(result.status_code, 200)
        self.assertEqual(ReviewLog.query.one().content_version, 1)

    def test_invalid_requests_cannot_fall_back_to_unversioned_rating(self):
        body = self.rate_input()
        cases = [None, [], {}, dict(body, user_id=2), dict(body, content_version=None),
                 dict(body, content_version=True), dict(body, expected_revision=None), dict(body, request_id=None),
                 dict(body, card_id='other:q'), dict(body, rating=True)]
        for bad in cases:
            with self.subTest(bad=bad):
                self.assertEqual(self.call('POST', CONCEPT + '/rate', bad).status_code, 400)
        for query in ('', 'card_id=x&content_version=1&expected_revision=-1',
                      'card_id=idempotency:timeout&content_version=1&expected_revision=0&content_version=2'):
            self.assertEqual(self.call('GET', CONCEPT + '/review/reveal?' + query).status_code, 400)
        self.assertEqual(ReviewLog.query.count(), 0)
        self.assertEqual(self.call('GET', BASE + '/idempotent-order-api').status_code, 404)

    def test_drafts_and_hosted_owner_boundary_apply_to_every_new_route(self):
        for row in ContentRevision.query.all():
            row.published_at = row.reviewed_by = row.reviewed_on = None
        self.user.email_verified = True
        db.session.commit()
        self.assertEqual(self.call('GET', BASE).json['concepts'], [])
        self.assertEqual(self.call('GET', CONCEPT).status_code, 404)
        drafts = [(row.item_id, row.version, row.checksum) for row in ContentRevision.query.all()]
        with patch.dict(self.app.config, LEARNING_HOSTED_PILOT=True, LEARNING_HOSTED_OWNER_ID=1,
                        LEARNING_AI_OWNER_EMAIL=self.user.email, LEARNING_HOSTED_DRAFT_REVISIONS=drafts):
            self.assertTrue(self.call('GET', BASE).json['concepts'][0]['draft'])
            detail = self.call('GET', CONCEPT)
            self.assertTrue(detail.json['concept']['private_pilot_draft'])
            self.assertEqual(detail.headers['X-Learning-Content-Status'], 'private-draft-pilot')
            for method, path in [('GET', BASE), ('GET', CONCEPT), ('GET', CONCEPT + '/review'),
                                 ('GET', CONCEPT + '/review/reveal'), ('POST', CONCEPT + '/rate')]:
                self.assertEqual(self.call(method, path, {}, user=2).status_code, 404)
                self.assertEqual(self.client.open(path, method=method, base_url='https://localhost').status_code, 401)
            self.assertEqual(UserConceptProgress.query.count(), 0)
            self.assertEqual(ReviewLog.query.count(), 0)

    def test_lost_rating_response_can_be_recovered_without_another_write(self):
        original = learning_service.rate_card_for_user
        def lost(**kwargs):
            original(**kwargs)
            raise OperationalError('fixture', {}, Exception('lost after commit'))
        body = self.rate_input()
        with patch.object(learning_service, 'rate_card_for_user', side_effect=lost), self.assertLogs('project', 'WARNING'):
            self.assertEqual(self.call('POST', CONCEPT + '/rate', body).status_code, 503)
        recovered = self.call('GET', '/api/v1/learning/ratings/' + body['request_id']).json['receipt']
        self.assertEqual(recovered['content_version'], 1)
        self.assertEqual(ReviewLog.query.count(), 1)
        self.assertEqual(recovered, self.call('POST', CONCEPT + '/rate', body).json)

    def test_web_bookmark_and_mobile_bookmark_cannot_silently_overwrite(self):
        first = self.call('POST', CONCEPT + '/enrollment', {}).json['progress']
        payload = dict(content_version=1, section_id='retries', expected_revision=first['revision'], request_id=str(uuid4()))
        saved = concept_progress_service.save_position(1, 'idempotency', **payload)
        other = dict(payload, section_id='design', request_id=str(uuid4()))
        self.assertEqual(self.call('PUT', CONCEPT + '/reading-position', other).status_code, 409)
        self.assertEqual(self.call('GET', CONCEPT).json['progress'], saved)
        self.assertEqual(self.call('POST', CONCEPT + '/enrollment', {}).json['progress'], saved)
