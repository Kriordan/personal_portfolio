from flask_apscheduler import APScheduler
from flask_login import LoginManager
from flask_migrate import Migrate
from flask_talisman import Talisman

login_manager = LoginManager()
migrate = Migrate()
scheduler = APScheduler()
talisman = Talisman()
