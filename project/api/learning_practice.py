"""JSON practice-session endpoints for API clients (JWT). Same service as the website."""
from __future__ import annotations

from flask import Blueprint, current_app, jsonify, request
from flask_jwt_extended import jwt_required
from sqlalchemy.exc import OperationalError, SQLAlchemyError
from werkzeug.exceptions import RequestEntityTooLarge

from project.api.learning import _current_user_from_jwt
from project.database import db
from project.services import learning_service, practice_service as practice

practice_api_blueprint = Blueprint("api_learning_practice", __name__, url_prefix="/learning/practice")
PRACTICE_REQUEST_BYTES = 2 * 1024 * 1024


@practice_api_blueprint.before_request
def guard_practice_api():
    if not practice.enabled():
        return jsonify({"error": "Not found."}), 404
    request.max_content_length = PRACTICE_REQUEST_BYTES
    return None


@practice_api_blueprint.after_request
def private_practice_response(response):
    response.headers["Cache-Control"] = "private, no-store"
    return response


@practice_api_blueprint.errorhandler(RequestEntityTooLarge)
def too_large(_error):
    return jsonify({"error": "Practice requests must be 2 MiB or less.", "code": "too_large"}), 413


def _error(message, status, code, **extra):
    return jsonify({"error": message, "code": code, **extra}), status


def _call(operation):
    """Run a service call and map its failures to stable JSON errors."""
    try:
        return operation()
    except learning_service.NotFoundError:
        return _error("Not found.", 404, "not_found")
    except practice.PracticeValidationError as exc:
        return _error(exc.message, 400, "invalid_request", field=exc.field)
    except learning_service.ValidationError:
        return _error("Invalid request.", 400, "invalid_request")
    except practice.StaleArtifactError as exc:
        return _error("An artifact changed elsewhere. Nothing was saved.", 409, "stale_artifact",
                      conflicts=exc.conflicts)
    except practice.RequestConflictError:
        return _error("This request ID was already used for a different change.", 409, "request_conflict")
    except OperationalError as exc:
        db.session.rollback()
        current_app.logger.error("Practice API request could not be confirmed: %s", practice.describe_failure(exc))
        return _error("The result could not be confirmed. Retry with the same request_id.", 503, "unavailable",
                      retry_same_request=True)
    except SQLAlchemyError as exc:
        db.session.rollback()
        current_app.logger.error("Practice API request failed: %s", practice.describe_failure(exc))
        return _error("The request failed and was not saved.", 503, "failed", retry_same_request=False)


def _user_and_payload(*, body=True):
    user = _current_user_from_jwt()
    if user is None:
        return None, None, _error("Unauthorized.", 401, "unauthorized")
    if not body:
        return user, None, None
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return user, None, _error("Send a JSON object.", 400, "invalid_request")
    return user, payload, None


@practice_api_blueprint.get("/sessions")
@jwt_required()
def list_sessions():
    user, _, failure = _user_and_payload(body=False)
    return failure or _call(lambda: (jsonify({"sessions": practice.list_sessions(user.id)}), 200))


@practice_api_blueprint.post("/sessions")
@jwt_required()
def start_session():
    user, payload, failure = _user_and_payload()
    if failure:
        return failure
    if set(payload) - {"exercise_id", "concept_id", "request_id"}:
        return _error("Unknown fields.", 400, "invalid_request")
    return _call(lambda: (jsonify(practice.start_session(
        user, exercise_id=payload.get("exercise_id"), concept_id=payload.get("concept_id"),
        request_id=payload.get("request_id"))), 201))


@practice_api_blueprint.get("/sessions/<session_id>")
@jwt_required()
def session_detail(session_id):
    user, _, failure = _user_and_payload(body=False)
    return failure or _call(lambda: (jsonify(practice.session_detail(user.id, session_id)), 200))


@practice_api_blueprint.put("/sessions/<session_id>/artifacts/<artifact_id>")
@jwt_required()
def save_artifact(session_id, artifact_id):
    user, payload, failure = _user_and_payload()
    if failure:
        return failure
    if set(payload) != {"request_id", "base_revision", "language", "body"}:
        return _error("Send request_id, base_revision, language, and body.", 400, "invalid_request")
    edit = {"artifact_id": artifact_id, "base_revision": payload["base_revision"],
            "language": payload["language"], "body": payload["body"]}
    return _call(lambda: (jsonify(practice.save_artifacts(
        user, session_id, edits=[edit], request_id=payload["request_id"])), 200))


@practice_api_blueprint.get("/sessions/<session_id>/artifacts/<artifact_id>/revisions")
@jwt_required()
def artifact_history(session_id, artifact_id):
    user, _, failure = _user_and_payload(body=False)
    return failure or _call(lambda: (jsonify(practice.artifact_history(user.id, session_id, artifact_id)), 200))


@practice_api_blueprint.get("/sessions/<session_id>/artifacts/<artifact_id>/revisions/<int:revision>")
@jwt_required()
def artifact_revision(session_id, artifact_id, revision):
    user, _, failure = _user_and_payload(body=False)
    return failure or _call(lambda: (jsonify(practice.artifact_revision(
        user.id, session_id, artifact_id, revision)), 200))


@practice_api_blueprint.get("/receipts/<request_id>")
@jwt_required()
def receipt(request_id):
    user, _, failure = _user_and_payload(body=False)
    # No receipt is not proof that an in-flight transaction cannot still commit.
    return failure or _call(lambda: (jsonify({"receipt": practice.practice_receipt(user.id, request_id)}), 200))
