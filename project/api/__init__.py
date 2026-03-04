"""API blueprint registration for mobile and external clients."""

from flask import Blueprint

from project.api.auth import auth_api_blueprint
from project.api.lists import lists_api_blueprint

api_blueprint = Blueprint("api", __name__, url_prefix="/api/v1")
api_blueprint.register_blueprint(auth_api_blueprint)
api_blueprint.register_blueprint(lists_api_blueprint)

