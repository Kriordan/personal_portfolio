from flask import Blueprint, current_app
from flask_login import current_user
from project.learning.access import private_response, require_web_access

learning_blueprint = Blueprint(
    "learning", __name__, url_prefix="/learning", template_folder="templates"
)
learning_blueprint.after_request(private_response)


@learning_blueprint.before_request
def require_learning_login():
    """Protect the entire study area, including newly added routes, by default."""
    if not current_user.is_authenticated:
        return current_app.login_manager.unauthorized()
    require_web_access(current_user)


from . import practice_views, views, feedback_views, progress_views, self_assessment_views  # noqa: E402,F401
