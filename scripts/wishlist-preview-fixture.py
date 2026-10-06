"""Disposable native UI fixture. Never loads dotenv, production DBs, or AWS.

Run with the locked application environment from the repository root:
  poetry run python scripts/wishlist-preview-fixture.py
The script prints disposable credentials and removes its data when stopped.
Android: adb reverse tcp:5057 tcp:5057 (use localhost for the API and photo URLs).
"""

import os
import sys
import tempfile
from datetime import timedelta
from pathlib import Path
from uuid import uuid4

os.environ["PYTHON_DOTENV_DISABLED"] = "1"
os.environ["AWS_EC2_METADATA_DISABLED"] = "true"
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from flask import send_from_directory  # noqa: E402
from project import create_app  # noqa: E402
from project.database import db  # noqa: E402
from project.extensions import talisman  # noqa: E402
from project.models import Gift, User  # noqa: E402
from project.services import wishlist_service  # noqa: E402
from project.sockets import socketio  # noqa: E402


def main():
    with tempfile.TemporaryDirectory(prefix="wishlist-preview-") as directory:
        root = Path(directory)
        photos = root / "photos"
        photos.mkdir()
        app = create_app({
            "TESTING": True,
            "SECRET_KEY": "disposable-wishlist-preview-only",
            "JWT_SECRET_KEY": "disposable-wishlist-preview-jwt-secret-only",
            "SQLALCHEMY_DATABASE_URI": f"sqlite:///{root / 'preview.sqlite'}",
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "JWT_ACCESS_TOKEN_EXPIRES": timedelta(seconds=10),
            "JWT_REFRESH_TOKEN_EXPIRES": timedelta(days=1),
            "WTF_CSRF_ENABLED": False,
            "SESSION_COOKIE_SECURE": False,
            "RATELIMIT_ENABLED": False,
        })
        talisman.force_https = False

        def fixture_upload(file):
            # Exercise real decoding/normalization; store only in this temporary fixture.
            image, extension, _content_type = wishlist_service.prepare_image(file)
            filename = f"{uuid4().hex}.{extension}"
            (photos / filename).write_bytes(image.read())
            return f"http://127.0.0.1:5057/fixture/photos/{filename}"

        wishlist_service.upload_image_to_s3 = fixture_upload

        @app.get("/fixture/photos/<filename>")
        def fixture_photo(filename):
            return send_from_directory(photos, filename)

        with app.app_context():
            db.create_all()
            user = User(email="wishlist-preview@example.test", username="Wishlist Preview", email_verified=True)
            user.set_password("WishlistPreview123!")
            db.session.add(user)
            db.session.flush()
            db.session.add_all([
                Gift(title="Weekend coffee grinder", body="A small hand grinder for slow Saturday mornings.", user_id=user.id),
                Gift(title="A field guide to local birds", body="Pocket size, with illustrations and room for notes.", user_id=user.id),
                Gift(title="Ceramic breakfast bowl", body="Warm oatmeal glaze, made by a local potter.", user_id=user.id),
            ])
            db.session.commit()
        print("Disposable login: wishlist-preview@example.test / WishlistPreview123!", flush=True)
        print(f"Temporary data: {root}", flush=True)
        socketio.run(app, host="127.0.0.1", port=5057, allow_unsafe_werkzeug=True, use_reloader=False)


if __name__ == "__main__":
    main()
