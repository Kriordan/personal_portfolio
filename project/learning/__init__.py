from flask import Blueprint

learning_blueprint = Blueprint(
    "learning", __name__, url_prefix="/learning", template_folder="templates"
)

from . import views  # noqa: E402,F401
