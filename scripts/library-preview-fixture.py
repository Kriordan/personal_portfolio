"""Disposable Library UI fixture. No production DB, OAuth, YouTube, or S3 calls.

Run with the locked Python environment. HTTP API: http://127.0.0.1:5057.
POST /fixture/state with {"sync": "success|unavailable|upstream|unexpected",
"reads": "success|failure|empty", "delay": 2} to exercise recovery.
All data and artwork are removed on exit. Android needs adb reverse for API/Metro.
"""
import io
import os
import sys
import tempfile
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

os.environ["PYTHON_DOTENV_DISABLED"] = "1"
os.environ["AWS_EC2_METADATA_DISABLED"] = "true"
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from flask import jsonify, request, send_file  # noqa: E402
from google.auth.exceptions import TransportError  # noqa: E402
from PIL import Image, ImageDraw  # noqa: E402
from project import create_app  # noqa: E402
from project.database import db  # noqa: E402
from project.extensions import talisman  # noqa: E402
from project.library.jobs import YouTubeConfigurationError  # noqa: E402
from project.models import Gift, Playlist, User, Video  # noqa: E402
from project.sockets import socketio  # noqa: E402


def main():
    with tempfile.TemporaryDirectory(prefix="library-preview-") as directory:
        app = create_app({
            "TESTING": True,
            "SECRET_KEY": "disposable-library-preview-only",
            "JWT_SECRET_KEY": "disposable-library-preview-jwt-secret-only",
            "SQLALCHEMY_DATABASE_URI": f"sqlite:///{Path(directory) / 'preview.sqlite'}",
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "JWT_ACCESS_TOKEN_EXPIRES": timedelta(seconds=10),
            "JWT_REFRESH_TOKEN_EXPIRES": timedelta(days=1),
            "WTF_CSRF_ENABLED": False,
            "SESSION_COOKIE_SECURE": False,
            "RATELIMIT_ENABLED": False,
        })
        talisman.force_https = False
        mode = {"sync": "success", "reads": "success", "delay": 2}
        now = datetime.now(timezone.utc)
        with app.app_context():
            db.create_all()
            for number in (1, 2):
                user = User(email=f"library{number}@example.test", username=f"Library Preview {number}", email_verified=True)
                user.set_password("LibraryPreview123!")
                db.session.add(user)
                db.session.flush()
                db.session.add(Gift(user_id=user.id, title="Library regression gift", body="A disposable text-only gift."))
            for id, title, description, thumbnail in [
                ("pl-music", "A little room for music", "Piano, small performances, and ideas worth returning to. " * 5, "http://127.0.0.1:5057/fixture/art/music"),
                ("pl-making", "The joy of making things", "Thoughtful design, practical craft, and a fresh perspective.", "http://127.0.0.1:5057/fixture/art/making"),
                ("pl-empty", "A collection for later", None, None),
                ("pl-broken", "A long playlist title that should wrap comfortably on a smaller phone at the largest text size", "A missing thumbnail should keep its place.", "http://127.0.0.1:5057/fixture/missing.jpg"),
            ]:
                db.session.add(Playlist(id=id, title=title, description=description, published_at=now, updated_at=now, thumbnail_url=thumbnail))
            db.session.flush()
            for index in range(150):
                db.session.add(Video(
                    id=f"video-{index}", playlist_id="pl-music", video_url_id="" if index == 2 else "aqz-KE-bpKQ",
                    title=["A quiet morning at the piano", "Listening closely: a small performance", "A video without a watch link"][index] if index < 3 else f"Practice session {index + 1}: finding a little more space in the music",
                    description=f"Music practice and composition, session {index + 1}",
                    published_at=now - timedelta(days=index),
                    thumbnail_url="http://127.0.0.1:5057/fixture/art/music" if index % 3 == 0 else None,
                    embed_url="https://www.youtube.com/embed/aqz-KE-bpKQ", watched=index == 1,
                ))
            db.session.commit()

        @app.post("/fixture/state")
        def state():
            values = request.get_json()
            mode.update({key: values[key] for key in mode if key in values})
            return jsonify(mode)

        @app.before_request
        def read_failure():
            if request.path.startswith("/api/v1/library/") and request.method == "GET":
                if mode["reads"] == "failure":
                    return jsonify({"error": "Fixture read unavailable"}), 503
                if mode["reads"] == "empty" and request.path.endswith("/playlists"):
                    return jsonify({"playlists": []})

        @app.get("/fixture/art/<name>")
        def art(name):
            image = Image.new("RGB", (320, 180), "#e4cdae" if name == "music" else "#c7d4c5")
            draw = ImageDraw.Draw(image)
            for index in range(6):
                x = 45 + index * 39
                draw.rounded_rectangle((x, 38, x + 22, 144), radius=6, fill="#505c56" if name == "music" else "#677c72")
            data = io.BytesIO()
            image.save(data, "PNG")
            data.seek(0)
            return send_file(data, mimetype="image/png")

        def sync():
            time.sleep(float(mode["delay"]))
            if mode["sync"] == "unavailable":
                raise YouTubeConfigurationError("Fixture credentials unavailable")
            if mode["sync"] == "upstream":
                raise TransportError("Fixture upstream failure")
            if mode["sync"] == "unexpected":
                raise RuntimeError("Fixture unexpected failure")
            playlist = db.session.get(Playlist, "pl-making")
            playlist.description = "Updated by the disposable YouTube import."
            playlist.updated_at = datetime.now(timezone.utc)
            db.session.commit()

        print("Disposable logins: library1@example.test or library2@example.test / LibraryPreview123!", flush=True)
        with patch("project.services.library_service.sync_playlists_and_videos", sync):
            socketio.run(app, host="127.0.0.1", port=5057, allow_unsafe_werkzeug=True, use_reloader=False)


if __name__ == "__main__":
    main()
