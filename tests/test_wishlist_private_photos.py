import html
import io
import os
from datetime import datetime, timedelta, timezone
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

import boto3
from botocore.config import Config
from botocore.exceptions import NoCredentialsError

from test_api_wishlist import WishlistTestCase
from project import create_app, wishlist_storage as storage
from project.csp import build_csp
from project.database import db
from project.models import Gift
from project.services import wishlist_service as service

BUCKET = "wishlist-private-test"
KEY = "w/" + "a" * 32 + ".jpg"
STORED = f"https://{BUCKET}.s3.amazonaws.com/{KEY}"
NOW = datetime(2026, 10, 6, 12, tzinfo=timezone.utc)


class PrivateWishlistPhotoTests(WishlistTestCase):
    def setUp(self):
        super().setUp()
        self.env = patch.dict(os.environ, {"WISHLIST_S3_BUCKET": BUCKET, "WISHLIST_S3_REGION": "us-west-2"})
        self.env.start()
        self.addCleanup(self.env.stop)
        # Real botocore signing, explicit dummy credentials; no AWS requests.
        self.s3 = boto3.client("s3", region_name="us-west-2", aws_access_key_id="testing",
                               aws_secret_access_key="testing", config=Config(signature_version="s3v4", s3={"addressing_style": "virtual"}))
        self.client_patch = patch("project.wishlist_storage.s3_client", return_value=self.s3)
        self.mock_client = self.client_patch.start()
        self.addCleanup(self.client_patch.stop)
        self.owner = self._create_user(email="private@example.com", username="private")
        self.other = self._create_user(email="other@example.com", username="other")
        self.gift_id = self._create_gift(user_id=self.owner)
        self.path = f"/api/v1/wishlist/gifts/{self.gift_id}"
        self.headers = self._auth_headers(self.owner)
        with self.app.app_context():
            db.session.get(Gift, self.gift_id).image_url = STORED
            db.session.commit()

    def check_signed(self, url):
        parsed = urlsplit(url)
        self.assertEqual(parsed.scheme, "https")
        self.assertEqual(parsed.netloc, f"{BUCKET}.s3.us-west-2.amazonaws.com")
        self.assertEqual(parsed.path, f"/{KEY}")
        query = parse_qs(parsed.query)
        self.assertEqual(query["X-Amz-Expires"], ["900"])
        self.assertIn("/us-west-2/s3/aws4_request", query["X-Amz-Credential"][0])
        self.assertEqual(query["response-cache-control"], ["private, no-store"])
        self.assertTrue(query["X-Amz-Signature"][0])
        return query

    def test_owner_gets_signed_url_and_database_keeps_permanent_reference(self):
        response = self._get(self.path, headers=self.headers)
        self.check_signed(response.json["gift"]["image_url"])
        self.assertEqual(response.headers["Cache-Control"], "private, no-store")
        with self.app.app_context():
            self.assertEqual(db.session.get(Gift, self.gift_id).image_url, STORED)

    def test_signing_never_runs_for_unauthenticated_or_foreign_access(self):
        self.assertEqual(self._get(self.path).status_code, 401)
        other_headers = self._auth_headers(self.other)
        self.assertEqual(self._get(self.path, headers=other_headers).status_code, 404)
        self.assertEqual(self._put(self.path, headers=other_headers, json={"title": "Stolen"}).status_code, 404)
        self.assertEqual(self._get("/api/v1/wishlist/gifts", headers=other_headers).json["gifts"], [])
        with self.app.app_context():
            with self.assertRaises(PermissionError):
                service.serialize_gift(db.session.get(Gift, self.gift_id), user_id=self.other)
        self.mock_client.assert_not_called()

    def test_each_read_renews_expiry_without_persisting_bearer_url(self):
        urls = []
        for moment in (NOW, NOW + timedelta(minutes=16)):
            with patch("botocore.auth.get_current_datetime", return_value=moment):
                url = self._get(self.path, headers=self.headers).json["gift"]["image_url"]
            query = self.check_signed(url)
            self.assertEqual(query["X-Amz-Date"], [moment.strftime("%Y%m%dT%H%M%SZ")])
            urls.append(url)
        self.assertNotEqual(urls[0], urls[1])
        with self.app.app_context():
            self.assertEqual(db.session.get(Gift, self.gift_id).image_url, STORED)

    def test_create_update_and_list_return_signed_photos(self):
        with patch.object(service, "upload_image_to_s3", return_value=STORED):
            response = self._post("/api/v1/wishlist/gifts", headers=self.headers, data={
                "title": "Created", "body": "Private photo", "image": (io.BytesIO(b"mock upload"), "image.jpg"),
            })
        self.assertEqual(response.status_code, 201)
        self.check_signed(response.json["gift"]["image_url"])
        self.check_signed(self._put(self.path, headers=self.headers, json={"body": "Edited"}).json["gift"]["image_url"])
        gifts = self._get("/api/v1/wishlist/gifts", headers=self.headers).json["gifts"]
        self.assertEqual(len(gifts), 2)
        for gift in gifts:
            self.check_signed(gift["image_url"])
        with self.app.app_context():
            self.assertTrue(all(gift.image_url == STORED for gift in db.session.query(Gift).all()))

    def test_signer_is_not_a_general_bucket_or_object_signing_service(self):
        untrusted = [
            None, "https://example.com/original.jpg", STORED.replace(BUCKET, "other-bucket"),
            STORED.replace("/w/", "/other/"), STORED.replace("/w/", "/w/../"),
            STORED.replace("https://", "http://"), STORED + "?download=1", STORED + "#fragment",
            STORED.replace(".com/", ".com.evil.test/"), STORED.replace("/w/", "/w/%2e%2e/"),
        ]
        for url in untrusted:
            self.assertEqual(storage.photo_url(url), url)
        self.mock_client.assert_not_called()
        for origin in storage.image_origins():
            self.check_signed(storage.photo_url(f"{origin}/{KEY}"))

    def test_signing_outage_does_not_turn_committed_save_into_failure(self):
        self.mock_client.side_effect = NoCredentialsError()
        with self.assertLogs("project.wishlist_storage", level="WARNING"):
            response = self._put(self.path, headers=self.headers, json={"title": "Saved"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["gift"]["title"], "Saved")
        self.assertEqual(response.json["gift"]["image_url"], STORED)
        self.assertNotIn("credentials", response.get_data(as_text=True))
        self.assertEqual(self._put(self.path, headers=self.headers, json={"remove_image": True}).status_code, 200)

    def test_website_signs_only_owned_photos_and_prevents_response_caching(self):
        with self.client.session_transaction() as session:
            session["_user_id"] = str(self.owner)
            session["_fresh"] = True
        for path in ("/wishlist/", f"/wishlist/gifts/{self.gift_id}/delete"):
            response = self._get(path)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.headers["Cache-Control"], "private, no-store")
            self.assertIn("X-Amz-Signature=", html.unescape(response.get_data(as_text=True)))
        with self.client.session_transaction() as session:
            session["_user_id"] = str(self.other)
        self.mock_client.reset_mock()
        self.assertEqual(self._get(f"/wishlist/gifts/{self.gift_id}/delete").status_code, 404)
        self.assertNotIn("X-Amz-Signature", self._get("/wishlist/").get_data(as_text=True))
        self.mock_client.assert_not_called()

    def test_csp_is_resolved_per_app_and_allows_only_configured_image_hosts(self):
        app = create_app({**self.app.config, "TESTING": True})
        response = app.test_client().get("/", base_url="https://localhost")
        policy = response.headers["Content-Security-Policy"]
        self.assertIn(f"https://{BUCKET}.s3.us-west-2.amazonaws.com", policy)
        self.assertNotIn("*.s3", policy)
        with patch.dict(os.environ, {"WISHLIST_S3_BUCKET": "another-bucket"}):
            self.assertNotIn(STORED.rsplit("/w/", 1)[0], build_csp()["img-src"])

    def test_storage_client_uses_explicit_region_and_signature_v4(self):
        self.client_patch.stop()
        with patch("project.wishlist_storage.boto3.client") as client:
            storage.s3_client()
        self.assertEqual(client.call_args.kwargs["region_name"], "us-west-2")
        self.assertEqual(client.call_args.kwargs["config"].signature_version, "s3v4")
