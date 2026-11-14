"""Disposable sign-in for interval simulator checks; never uses production data."""
import os
import signal
import sys
import tempfile
from datetime import timedelta
from pathlib import Path

os.environ["PYTHON_DOTENV_DISABLED"] = "1"
os.environ["AWS_EC2_METADATA_DISABLED"] = "true"
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from project import create_app  # noqa: E402
from project.database import db  # noqa: E402
from project.extensions import talisman  # noqa: E402
from project.models import User  # noqa: E402
from project.sockets import socketio  # noqa: E402


def main():
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))
    with tempfile.TemporaryDirectory(prefix="interval-preview-") as directory:
        app = create_app({
            "TESTING": True,
            "SECRET_KEY": "disposable-interval-preview-only",
            "JWT_SECRET_KEY": "disposable-interval-preview-jwt-secret-only",
            "SQLALCHEMY_DATABASE_URI": f"sqlite:///{Path(directory) / 'preview.sqlite'}",
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "JWT_ACCESS_TOKEN_EXPIRES": timedelta(hours=2),
            "JWT_REFRESH_TOKEN_EXPIRES": timedelta(days=1),
            "WTF_CSRF_ENABLED": False,
            "SESSION_COOKIE_SECURE": False,
            "RATELIMIT_ENABLED": False,
        })
        talisman.force_https = False
        with app.app_context():
            db.create_all()
            user = User(email="intervals@example.test", username="Interval Preview", email_verified=True)
            user.set_password("IntervalPreview123!")
            db.session.add(user)
            db.session.commit()
        print("Disposable sign-in: intervals@example.test / IntervalPreview123!", flush=True)
        socketio.run(app, host="127.0.0.1", port=5097, allow_unsafe_werkzeug=True, use_reloader=False)


if __name__ == "__main__":
    main()
