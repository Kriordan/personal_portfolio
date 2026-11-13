"""Optional owner-only boundary for a hosted Learning pilot.

Both identity and verified email must match. An incomplete pilot configuration
closes Learning without changing authentication or access to the rest of the site.
"""
from flask import abort, current_app, g, jsonify
from flask_jwt_extended import verify_jwt_in_request


def allowed(user):
    if not user or not user.is_authenticated:
        return False
    if not current_app.config.get("LEARNING_HOSTED_PILOT"):
        return True
    owner = current_app.config.get("LEARNING_HOSTED_OWNER_ID")
    email = current_app.config.get("LEARNING_AI_OWNER_EMAIL")
    return (type(owner) is int and owner > 0 and user.id == owner and user.email_verified
            and isinstance(email, str) and bool(email.strip())
            and user.email.strip().lower() == email.strip().lower())


def require_web_access(user):
    if not allowed(user):
        abort(404)
    g.learning_owner_allowed = True


def require_api_access():
    if not current_app.config.get("LEARNING_HOSTED_PILOT"):
        return None
    # JWT authentication remains independent of the browser's login cookie.
    verify_jwt_in_request()
    from project.api.learning import _current_user_from_jwt
    if not allowed(_current_user_from_jwt()):
        return jsonify(error="Not found."), 404
    g.learning_owner_allowed = True
    return None


def private_response(response):
    response.headers["Cache-Control"] = "private, no-store"
    response.headers["X-Robots-Tag"] = "noindex, nofollow"
    if current_app.config.get("LEARNING_HOSTED_PILOT") and getattr(g, "learning_owner_allowed", False):
        response.headers["X-Learning-Content-Status"] = "private-draft-pilot"
    return response
