"""JSON practice-session endpoints for API clients (JWT). Same service as the website."""
from __future__ import annotations

from flask import Blueprint, current_app, jsonify, make_response, request
from flask_jwt_extended import jwt_required
from sqlalchemy.exc import OperationalError, SQLAlchemyError
from werkzeug.exceptions import RequestEntityTooLarge

from project.api.learning import _current_user_from_jwt
from project.learning.access import private_response, require_api_access
from project.database import db
from project.services import feedback_service, feedback_review_service, learning_service, practice_service as practice, practice_export_service

practice_api_blueprint = Blueprint("api_learning_practice", __name__, url_prefix="/learning/practice")
practice_api_blueprint.before_request(require_api_access)
practice_api_blueprint.after_request(private_response)
PRACTICE_REQUEST_BYTES = 2 * 1024 * 1024
TURN_FIELDS = {"request_id", "body", "expected_sequence", "artifact_revisions", "brief_revision"}
# What to tell a client when the database fails. Only POST and PUT carry a request_id.
UNCONFIRMED = {
    "POST": "The result could not be confirmed. Retry with the same request_id.",
    "PUT": "The result could not be confirmed. Retry with the same request_id.",
    "DELETE": "The result could not be confirmed. Repeat the request: a 404 then means the session was deleted.",
    "GET": "The service is unavailable. Try again.",
}
FAILED = {"POST": "The request failed and was not saved.", "PUT": "The request failed and was not saved.",
          "DELETE": "The request failed and nothing was deleted.", "GET": "The request failed. Try again."}
STALE_MESSAGES = {
    "stale_artifact": "An artifact changed elsewhere. Nothing was saved.",
    "stale_brief": "The brief changed elsewhere. Nothing was saved.",
    "stale_transcript": "New turns arrived after this view loaded. Nothing was saved.",
    "out_of_date": "This view of the session is out of date. Nothing was saved.",
}


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
    except practice_export_service.ExportTooLarge:
        return _error("This session exceeds the download size allowance. Nothing was omitted or changed.",
                      413, "export_too_large")
    except practice.PracticeValidationError as exc:
        return _error(exc.message, 400, "invalid_request", field=exc.field, part=exc.part)
    except learning_service.ValidationError:
        return _error("Invalid request.", 400, "invalid_request")
    except practice.StaleViewError as exc:
        return _error(STALE_MESSAGES[exc.code], 409, exc.code, **exc.details())
    except practice.RequestConflictError:
        return _error("This request ID was already used for a different change.", 409, "request_conflict")
    except feedback_review_service.AnnotationConflict as exc:
        return _error("Your response changed elsewhere. Compare both versions before saving.", 409,
                      "stale_annotation", annotation=exc.current)
    except feedback_review_service.DecisionRequired:
        return _error("Agree with this concern before rating its follow-up practice.", 409, "decision_required")
    except practice.FeedbackPendingError:
        return _error("Feedback is being prepared. You can still save edits; try again when it finishes.", 409, "feedback_pending")
    except practice.ReplyPendingError:
        return _error("The interviewer is still replying. Try again once the reply arrives.", 409, "reply_pending")
    except learning_service.ConflictError:
        return _error("This review changed or was already rated. Load the remaining practice.", 409, "stale_review")
    except OperationalError as exc:
        db.session.rollback()
        current_app.logger.error("Practice API request could not be confirmed: %s", practice.describe_failure(exc))
        return _error(UNCONFIRMED.get(request.method, UNCONFIRMED["POST"]), 503, "unavailable",
                      retry_same_request=True)
    except SQLAlchemyError as exc:
        db.session.rollback()
        current_app.logger.error("Practice API request failed: %s", practice.describe_failure(exc))
        return _error(FAILED.get(request.method, FAILED["POST"]), 503, "failed", retry_same_request=False)


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


@practice_api_blueprint.get("/sessions/<session_id>/export/<format>")
@jwt_required()
def export_session(session_id, format):
    user, _, failure = _user_and_payload(body=False)
    if failure:
        return failure

    def download():
        file = practice_export_service.export_file(user.id, session_id, format)
        response = make_response(file["data"])
        response.headers["Content-Type"] = file["mimetype"] + "; charset=utf-8"
        response.headers.set("Content-Disposition", "attachment", filename=file["filename"])
        response.headers["X-Content-Type-Options"] = "nosniff"
        return response

    return _call(download)


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
    return _call(lambda: (jsonify(practice.save_work(
        user, session_id, edits=[edit], request_id=payload["request_id"])), 200))


@practice_api_blueprint.put("/sessions/<session_id>/brief")
@jwt_required()
def save_brief(session_id):
    """Replace the learner's brief (the detail's session_brief) with a full snapshot."""
    user, payload, failure = _user_and_payload()
    if failure:
        return failure
    if set(payload) != {"request_id", "base_revision", "entries"}:
        return _error("Send request_id, base_revision, and entries.", 400, "invalid_request")
    brief = {"base_revision": payload["base_revision"], "entries": payload["entries"]}
    return _call(lambda: (jsonify(practice.save_work(
        user, session_id, brief=brief, request_id=payload["request_id"])), 200))


@practice_api_blueprint.post("/sessions/<session_id>/turns")
@jwt_required()
def send_turn(session_id):
    """Append a learner turn. Save first: the turn cites the revisions you are looking at."""
    user, payload, failure = _user_and_payload()
    if failure:
        return failure
    if set(payload) != TURN_FIELDS:
        return _error("Send request_id, body, expected_sequence, artifact_revisions, and brief_revision.", 400,
                      "invalid_request")
    def send():
        result = practice.send_turn(
            user, session_id, body=payload["body"], expected_sequence=payload["expected_sequence"],
            artifact_revisions=payload["artifact_revisions"], brief_revision=payload["brief_revision"],
            request_id=payload["request_id"])
        # 202 when a reply is on its way (poll GET .../reply), 201 when the turn was saved without one.
        # A replayed receipt from before replies existed has no "reply".
        return jsonify(result), 202 if result.get("reply", {}).get("status") == "pending" else 201
    return _call(send)


@practice_api_blueprint.get("/sessions/<session_id>/reply")
@jwt_required()
def reply_status(session_id):
    """The latest learner turn's reply, and every turn after ?after=<sequence>."""
    user, _, failure = _user_and_payload(body=False)
    if failure:
        return failure
    raw = request.args.get("after", "0")
    if not (raw.isascii() and raw.isdigit()):
        return _error("after must be a whole number.", 400, "invalid_request", field="after")
    return _call(lambda: (jsonify(practice.reply_updates(user.id, session_id, after=int(raw))), 200))


@practice_api_blueprint.post("/sessions/<session_id>/submissions")
@jwt_required()
def submit_work(session_id):
    """Atomically save all artifacts/brief and snapshot syntax checks; no AI generation."""
    user, payload, failure = _user_and_payload()
    if failure:
        return failure
    if set(payload) != {"request_id", "expected_sequence", "edits", "brief"}:
        return _error("Send request_id, expected_sequence, edits, and brief.", 400, "invalid_request")
    return _call(lambda: (jsonify(practice.save_and_submit(user, session_id, **payload)), 201))


@practice_api_blueprint.get("/sessions/<session_id>/submissions/<int:sequence>")
@jwt_required()
def submission_detail(session_id, sequence):
    user, _, failure = _user_and_payload(body=False)
    return failure or _call(lambda: (jsonify(practice.submission_detail(user.id, session_id, sequence)), 200))


@practice_api_blueprint.route("/sessions/<session_id>/submissions/<int:sequence>/feedback", methods=["GET", "POST"])
@jwt_required()
def snapshot_feedback(session_id, sequence):
    user, payload, failure = _user_and_payload(body=request.method == "POST")
    if failure:
        return failure
    if request.method == "GET":
        return _call(lambda: (jsonify(feedback_service.detail(user.id, session_id, sequence)), 200))
    if set(payload) != {"request_id"}:
        return _error("Send request_id only. Feedback uses the saved snapshot.", 400, "invalid_request")
    def queue():
        result = feedback_service.request_feedback(user, session_id, sequence, request_id=payload["request_id"])
        return jsonify(result), 202 if result["request"]["status"] in practice.LIVE else 200
    return _call(queue)


@practice_api_blueprint.put("/sessions/<session_id>/submissions/<int:sequence>/feedback/<finding_id>/response")
@jwt_required()
def feedback_annotation(session_id, sequence, finding_id):
    user, payload, failure = _user_and_payload()
    if failure:
        return failure
    if set(payload) != {"request_id", "expected_revision", "decision", "note"}:
        return _error("Send request_id, expected_revision, decision, and note.", 400, "invalid_request")
    return _call(lambda: (jsonify(feedback_review_service.annotate(user, session_id, sequence, finding_id, **payload)), 200))


@practice_api_blueprint.route("/sessions/<session_id>/submissions/<int:sequence>/feedback/<finding_id>/review", methods=["GET", "POST"])
@jwt_required()
def feedback_review(session_id, sequence, finding_id):
    user, payload, failure = _user_and_payload(body=request.method == "POST")
    if failure:
        return failure
    attempt_fields = {"request_id", "card_id", "content_version", "expected_revision"}
    if request.method == "POST":
        if set(payload) != attempt_fields | {"rating"}:
            return _error("Send a pinned question, progress revision, request_id, and rating.", 400, "invalid_request")
        return _call(lambda: (jsonify(feedback_review_service.rate_review(user, session_id, sequence, finding_id, **payload)), 200))
    if not request.args:
        return _call(lambda: (jsonify(feedback_review_service.review_detail(user.id, session_id, sequence, finding_id)), 200))
    if set(request.args) != attempt_fields:
        return _error("Reveal requires card_id, content_version, expected_revision, and request_id.", 400, "invalid_request")
    values = {key: request.args.get(key, type=int) if key in {"content_version", "expected_revision"}
              else request.args.get(key) for key in attempt_fields}
    return _call(lambda: (jsonify(feedback_review_service.review_card(user.id, session_id, sequence, finding_id, **values)), 200))


@practice_api_blueprint.post("/sessions/<session_id>/reply")
@jwt_required()
def ask_for_reply(session_id):
    """Retry a reply, or ask for one to a turn saved while AI was unavailable.

    With "context": "recent", continue with recent messages when the conversation no longer
    fits what the interviewer can read: later replies read from the earliest message that
    fits ("context_from_sequence" in the response). Nothing is deleted.

    202 when a reply is queued. 200 when none is: the turn already has a reply ("answered"),
    or AI can't reply now ("unavailable", with a reason). For "essential_too_large", the
    reply detail's too_large_part names what to shorten; a reply reads the work its turn
    was sent with, so shorten it, save, and send a new turn.
    """
    user, payload, failure = _user_and_payload()
    if failure:
        return failure
    if ("request_id" not in payload or set(payload) - {"request_id", "context", "expected_sequence"}
            or ("expected_sequence" in payload and payload["expected_sequence"] is None)):
        return _error('Send request_id, and context "recent" to continue with recent messages.', 400,
                      "invalid_request")

    def ask():
        result = practice.request_reply(user, session_id, request_id=payload["request_id"],
                                        context=payload.get("context"), expected_sequence=payload.get("expected_sequence"))
        return jsonify(result), 202 if result["reply"]["status"] == "pending" else 200
    return _call(ask)


def _set_status(session_id, status):
    user, payload, failure = _user_and_payload()
    if failure:
        return failure
    if set(payload) != {"request_id"}:
        return _error("Send request_id.", 400, "invalid_request")
    return _call(lambda: (jsonify(practice.set_status(
        user, session_id, status=status, request_id=payload["request_id"])), 200))


@practice_api_blueprint.post("/sessions/<session_id>/pause")
@jwt_required()
def pause_session(session_id):
    return _set_status(session_id, "paused")


@practice_api_blueprint.post("/sessions/<session_id>/resume")
@jwt_required()
def resume_session(session_id):
    return _set_status(session_id, "active")


@practice_api_blueprint.delete("/sessions/<session_id>")
@jwt_required()
def delete_session(session_id):
    """Delete the session and everything in it. Repeating the request finds nothing: 404."""
    user, _, failure = _user_and_payload(body=False)
    if failure:
        return failure

    def delete():
        practice.delete_session(user, session_id)
        return "", 204
    return _call(delete)


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
