import io
import os
from unittest.mock import patch

from botocore.exceptions import ClientError, NoCredentialsError
from PIL import Image, PngImagePlugin

from test_api_wishlist import WishlistTestCase
from project.database import db
from project.models import Gift
from project.services import wishlist_service as service


def photo(format="PNG", size=(24, 16)):
    output = io.BytesIO()
    image = Image.new("RGB", size, "orange")
    options = {}
    if format == "PNG":
        info = PngImagePlugin.PngInfo()
        info.add_text("private", "metadata-must-disappear")
        options["pnginfo"] = info
    image.save(output, format=format, **options)
    output.seek(0)
    return output


class WishlistPhotoTests(WishlistTestCase):
    def setUp(self):
        super().setUp()
        self.owner = self._create_user(email="photos@example.com", username="photos")
        self.headers = self._auth_headers(self.owner)
        self.gift_id = self._create_gift(user_id=self.owner)
        self.path = f"/api/v1/wishlist/gifts/{self.gift_id}"
        with self.app.app_context():
            db.session.get(Gift, self.gift_id).image_url = "https://example.com/original.jpg"
            db.session.commit()

    def gift(self):
        return self._get(self.path, headers=self.headers).get_json()["gift"]

    def upload(self, data=None, **fields):
        return self._put(self.path, headers=self.headers, data={
            "image": (data if data is not None else photo(), "same-filename.jpg"), **fields,
        }, content_type="multipart/form-data")

    @patch.dict(os.environ, {"WISHLIST_S3_BUCKET": "wishlist-test"})
    @patch("project.services.wishlist_service.boto3.client")
    def test_real_validation_unique_keys_metadata_and_remove(self, client):
        stored = []
        def upload(stream, bucket, key, ExtraArgs):
            stored.append((stream.read(), bucket, key, ExtraArgs))
        client.return_value.upload_fileobj.side_effect = upload
        for _ in range(2):
            self.assertEqual(self.upload(title="Updated").status_code, 200)
        self.assertNotEqual(stored[0][2], stored[1][2])
        self.assertNotIn("same-filename", stored[0][2])
        self.assertEqual(stored[0][3], {"ContentType": "image/png"})
        self.assertNotIn(b"metadata-must-disappear", stored[0][0])
        with Image.open(io.BytesIO(stored[0][0])) as image:
            self.assertEqual(image.size, (24, 16))
        url = self.gift()["image_url"]
        self.assertIn(stored[1][2], url)
        self._put(self.path, headers=self.headers, json={"body": "Changed"})
        self.assertEqual(self.gift()["image_url"], url)
        self._put(self.path, headers=self.headers, json={"remove_image": True})
        self.assertIsNone(self.gift()["image_url"])
        self._delete(self.path, headers=self.headers)
        client.return_value.delete_object.assert_not_called()

    def test_invalid_requests_are_atomic(self):
        before = self.gift()
        invalid = [
            {"title": "valid", "body": " "}, {"title": None}, {"body": []},
            {"body": "x" * 141}, {"title": 42}, {"remove_image": "true"},
            {"remove_image": 1}, {"remove_image": None}, [], None,
        ]
        for payload in invalid:
            with self.subTest(payload=payload):
                response = self._put(self.path, headers=self.headers, json=payload, content_type="application/json")
                self.assertEqual(response.status_code, 400)
                self.assertEqual(self.gift(), before)
        self.assertEqual(self.upload(remove_image="true").status_code, 400)
        self.assertEqual(self.upload(remove_image="yes").status_code, 400)
        self.assertEqual(self.gift(), before)

    def test_creating_another_gift_keeps_existing_ownership(self):
        for title in ("Second gift", "Third gift"):
            response = self._post("/api/v1/wishlist/gifts", headers=self.headers, json={"title": title, "body": "Description"})
            self.assertEqual(response.status_code, 201)
        gifts = self._get("/api/v1/wishlist/gifts", headers=self.headers).get_json()["gifts"]
        self.assertEqual(len(gifts), 3)
        self.assertTrue(all(gift["user_id"] == self.owner for gift in gifts))

    @patch("project.services.wishlist_service.boto3.client")
    def test_bad_images_never_reach_storage(self, client):
        before = self.gift()
        for data in [io.BytesIO(b"not an image"), io.BytesIO(), photo("GIF"),
                     io.BytesIO(b"x" * (service.MAX_IMAGE_BYTES + 1)), photo(size=(5001, 5000))]:
            with self.subTest(size=data.getbuffer().nbytes):
                self.assertEqual(self.upload(data, title="Must not save").status_code, 400)
                self.assertEqual(self.gift(), before)
        client.assert_not_called()

    @patch.dict(os.environ, {"WISHLIST_S3_BUCKET": "wishlist-test"})
    @patch("project.services.wishlist_service.boto3.client")
    def test_storage_errors_are_explicit_and_atomic(self, client):
        for error in [NoCredentialsError(), ClientError({"Error": {"Code": "AccessDenied", "Message": "private-storage-detail"}}, "PutObject")]:
            client.return_value.upload_fileobj.side_effect = error
            before = self.gift()
            with self.assertLogs(self.app.logger, level="ERROR"):
                response = self.upload(title="Must not save")
            self.assertEqual(response.status_code, 503)
            self.assertEqual(response.get_json()["error"], service.UPLOAD_MESSAGE)
            self.assertNotIn("private-storage-detail", response.get_data(as_text=True))
            self.assertEqual(self.gift(), before)

    @patch.dict(os.environ, {"WISHLIST_S3_BUCKET": ""})
    def test_missing_config_blocks_upload_but_not_text_or_removal(self):
        with self.assertLogs(self.app.logger, level="ERROR"):
            self.assertEqual(self.upload().status_code, 503)
        self.assertEqual(self._put(self.path, headers=self.headers, json={"title": "Updated"}).status_code, 200)
        self.assertEqual(self._put(self.path, headers=self.headers, data={"remove_image": "true"}).status_code, 200)
        self.assertIsNone(self.gift()["image_url"])

    def test_request_limit_and_text_boundary(self):
        response = self.upload(io.BytesIO(b"x" * service.MAX_REQUEST_BYTES))
        self.assertEqual(response.status_code, 413)
        self.assertIsInstance(response.get_json()["error"], str)
        response = self._put(self.path, headers=self.headers, json={"title": " " + "x" * 140 + " ", "body": "😀" * 140})
        self.assertEqual(response.status_code, 200)
        for flag in [True, False, "true"]:
            response = self._post("/api/v1/wishlist/gifts", headers=self.headers, json={"title": "x", "body": "y", "remove_image": flag})
            self.assertEqual(response.status_code, 400)

    def test_commit_failure_rolls_back_and_hides_details(self):
        before = self.gift()
        with patch.object(db.session, "commit", side_effect=ValueError("private-database-detail")):
            with self.assertLogs(self.app.logger, level="ERROR"):
                response = self._put(self.path, headers=self.headers, json={"title": "Must not save", "remove_image": True})
        self.assertEqual(response.status_code, 500)
        self.assertNotIn("private-database-detail", response.get_data(as_text=True))
        self.assertEqual(self.gift(), before)

    def test_website_retains_text_when_photo_upload_fails(self):
        with self.client.session_transaction() as session:
            session["_user_id"] = str(self.owner)
            session["_fresh"] = True
        with patch.dict(os.environ, {"WISHLIST_S3_BUCKET": ""}):
            with self.assertLogs(self.app.logger, level="ERROR"):
                response = self._post("/wishlist/", data={"title": "Retained title", "body": "Retained description", "image": (photo(), "image.png")})
        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        self.assertIn("Retained title", html)
        self.assertIn("Nothing was saved", html)
        with self.app.app_context():
            self.assertEqual(db.session.query(Gift).filter_by(user_id=self.owner).count(), 1)

    def test_jpeg_orientation_and_animation(self):
        source = Image.new("RGB", (20, 10), "blue")
        exif = Image.Exif()
        exif[274] = 6
        stream = io.BytesIO()
        source.save(stream, format="JPEG", exif=exif)
        stream.seek(0)
        normalized, extension, content_type = service.prepare_image(stream)
        with Image.open(normalized) as image:
            self.assertEqual(image.size, (10, 20))
            self.assertFalse(image.getexif())
        self.assertEqual((extension, content_type), ("jpg", "image/jpeg"))
        animated = io.BytesIO()
        source.save(animated, format="PNG", save_all=True, append_images=[Image.new("RGB", (20, 10), "red")])
        animated.seek(0)
        with self.assertRaises(service.ValidationError):
            service.prepare_image(animated)
