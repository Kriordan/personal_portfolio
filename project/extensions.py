from flask_apscheduler import APScheduler
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_login import LoginManager
from flask_migrate import Migrate
from flask_talisman import Talisman

limiter = Limiter(key_func=get_remote_address, default_limits=[])
login_manager = LoginManager()
migrate = Migrate()
scheduler = APScheduler()
talisman = Talisman()
