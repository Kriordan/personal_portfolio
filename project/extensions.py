from flask_login import LoginManager
from flask_migrate import Migrate
from flask_talisman import Talisman

login_manager = LoginManager()
migrate = Migrate()
talisman = Talisman()
