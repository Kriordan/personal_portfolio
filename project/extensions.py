from flask import request
from flask_apscheduler import APScheduler
from flask_jwt_extended import JWTManager
from flask_limiter import Limiter
from flask_login import LoginManager
from flask_migrate import Migrate
from flask_talisman import Talisman


def _get_real_ip() -> str:
    """Return the real client IP behind Cloudflare / reverse proxies."""
    return (
        request.headers.get("CF-Connecting-IP")
        or request.access_route[0]
        or request.remote_addr
    )


limiter = Limiter(key_func=_get_real_ip, default_limits=[])
login_manager = LoginManager()
migrate = Migrate()
scheduler = APScheduler()
talisman = Talisman()
jwt = JWTManager()
