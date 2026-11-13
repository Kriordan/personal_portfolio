"""JSON learning endpoints for API clients."""

from __future__ import annotations

from flask import Blueprint, current_app, jsonify, request
from flask_jwt_extended import get_jwt_identity, jwt_required

from project.database import db
from project.models import User
from project.learning.access import private_response, require_api_access
from project.services import concept_progress_service, curriculum_service, learning_service, self_assessment_service
from sqlalchemy.exc import SQLAlchemyError

learning_api_blueprint = Blueprint("api_learning", __name__, url_prefix="/learning")
learning_api_blueprint.before_request(require_api_access)
learning_api_blueprint.after_request(private_response)


@learning_api_blueprint.after_request
def private_learning_response(response):
    response.headers["Cache-Control"] = "private, no-store"
    return response


def _current_user_from_jwt() -> User | None:
    identity = get_jwt_identity()
    if identity is None:
        return None
    try:
        return db.session.get(User, int(identity))
    except (TypeError, ValueError):
        return None


@learning_api_blueprint.get("/notes")
@jwt_required()
def api_get_notes():
    user = _current_user_from_jwt()
    if user is None:
        return jsonify({"error": "Unauthorized."}), 401

    notes_dir = learning_service.notes_dir_for_root(current_app.root_path)
    notes = learning_service.load_notes(notes_dir)
    notes, total_due = learning_service.summarize_notes_for_user(notes, user_id=user.id)
    return jsonify({"notes": notes, "total_due": total_due}), 200


@learning_api_blueprint.get("/notes/<string:note_id>")
@jwt_required()
def api_get_note(note_id: str):
    user = _current_user_from_jwt()
    if user is None:
        return jsonify({"error": "Unauthorized."}), 401

    notes_dir = learning_service.notes_dir_for_root(current_app.root_path)
    try:
        note_data = learning_service.note_with_cards(notes_dir, note_id, user_id=user.id)
    except learning_service.NotFoundError:
        return jsonify({"error": "Note not found."}), 404
    return jsonify({"note": note_data}), 200


@learning_api_blueprint.get("/review")
@jwt_required()
def api_get_review():
    user = _current_user_from_jwt()
    if user is None:
        return jsonify({"error": "Unauthorized."}), 401

    notes_dir = learning_service.notes_dir_for_root(current_app.root_path)
    try:
        raw_limit = request.args.get("limit")
        if raw_limit is not None and not raw_limit.isdecimal():
            raise learning_service.ValidationError("invalid limit")
        page = learning_service.review_page(notes_dir, user_id=user.id,
            note_id=request.args.get("note_id"), limit=int(raw_limit) if raw_limit is not None else None)
    except learning_service.ValidationError:
        return jsonify({"error": "Invalid review options."}), 400
    except learning_service.NotFoundError:
        return jsonify({"error": "Note not found."}), 404
    return jsonify(page), 200


@learning_api_blueprint.post("/rate")
@jwt_required()
def api_rate_card():
    user = _current_user_from_jwt()
    if user is None:
        return jsonify({"error": "Unauthorized."}), 401

    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify({"error": "Invalid review request."}), 400
    if not payload.get("card_id") or payload.get("rating") is None:
        return jsonify({"error": "card_id and rating are required"}), 400
    if type(payload["rating"]) is not int:
        return jsonify({"error": "rating must be an integer"}), 400
    notes_dir = learning_service.notes_dir_for_root(current_app.root_path)
    try:
        response_data = learning_service.rate_card_for_user(
            user=user,
            notes_dir=notes_dir,
            **learning_service.rating_payload(payload),
        )
    except learning_service.InvalidRatingError:
        return jsonify({"error": "rating must be between 0 and 5"}), 400
    except learning_service.InvalidCardIdError:
        return jsonify({"error": "invalid card_id format"}), 400
    except learning_service.ValidationError:
        return jsonify({"error": "Invalid review request."}), 400
    except learning_service.NotFoundError:
        return jsonify({"error": "card not found"}), 404
    except learning_service.StaleReviewError:
        return jsonify({
            "error": "This card changed elsewhere. Load a fresh review queue.",
            "code": "stale_progress",
        }), 409
    except learning_service.ConflictError:
        return jsonify({
            "error": "This request ID was already used for a different rating.",
            "code": "request_conflict",
        }), 409
    return jsonify(response_data), 200


@learning_api_blueprint.get("/ratings/<string:request_id>")
@jwt_required()
def api_get_rating(request_id: str):
    user = _current_user_from_jwt()
    if user is None:
        return jsonify({"error": "Unauthorized."}), 401
    try:
        receipt = learning_service.rating_receipt(user, request_id)
    except learning_service.ValidationError:
        return jsonify({"error": "Invalid request ID."}), 400
    # No receipt is not proof that an in-flight transaction cannot commit.
    return jsonify({"receipt": receipt}), 200


def _concept_call(operation):
    """Mobile adapters use the web curriculum/scheduler and the same owner boundary."""
    user = _current_user_from_jwt()
    if user is None:
        return jsonify(error="Unauthorized."), 401
    try:
        return jsonify(operation(user))
    except learning_service.NotFoundError:
        return jsonify(error="Concept or question not found."), 404
    except learning_service.ValidationError:
        return jsonify(error="Invalid concept request."), 400
    except learning_service.ConflictError:
        return jsonify(error="This view changed elsewhere. Reload before continuing.", code="stale_progress"), 409
    except SQLAlchemyError as exc:
        db.session.rollback()
        current_app.logger.warning("Concept API operation unconfirmed: %s", type(exc).__name__)
        return jsonify(error="The result could not be confirmed. Retry the same request."), 503


@learning_api_blueprint.get("/concepts")
@jwt_required()
def api_concepts():
    def read(user):
        return {"concepts": [dict(id=item["id"], title=item["title"], version=item["version"],
            summary=item["content"]["summary"],
            draft=bool(item.get("private_pilot_draft") or item.get("local_draft")),
            progress=concept_progress_service.progress(user.id, item["id"]),
            due_count=len(curriculum_service.concept_review_queue(item, user_id=user.id)))
            for item in curriculum_service.published_concepts()]}
    return _concept_call(read)


@learning_api_blueprint.get("/concepts/<concept_id>")
@jwt_required()
def api_concept(concept_id):
    def read(user):
        item = concept_progress_service.published_concept(concept_id)
        return dict(concept=item, progress=concept_progress_service.progress(user.id, concept_id),
                    due_count=len(curriculum_service.concept_review_queue(item, user_id=user.id)))
    return _concept_call(read)


@learning_api_blueprint.get("/concepts/<concept_id>/review")
@jwt_required()
def api_concept_review(concept_id):
    def read(user):
        item = concept_progress_service.published_concept(concept_id)
        cards = curriculum_service.concept_review_queue(item, user_id=user.id)
        return dict(cards=cards, total_due=len(cards), progress=concept_progress_service.progress(user.id, concept_id))
    return _concept_call(read)


@learning_api_blueprint.get("/concepts/<concept_id>/review/reveal")
@jwt_required()
def api_concept_reveal(concept_id):
    def read(user):
        concept_progress_service.published_concept(concept_id)
        keys = {"card_id", "content_version", "expected_revision"}
        if set(request.args) != keys or any(len(request.args.getlist(key)) != 1 for key in keys):
            raise learning_service.ValidationError("Invalid reveal request.")
        values = {}
        for key, minimum in (("content_version", 1), ("expected_revision", 0)):
            raw = request.args[key]
            if not raw.isascii() or not raw.isdecimal() or len(raw) > 10:
                raise learning_service.ValidationError("Invalid reveal version.")
            values[key] = int(raw)
            if not minimum <= values[key] <= 2147483647:
                raise learning_service.ValidationError("Invalid reveal version.")
        card = curriculum_service.published_review_question(concept_id, request.args["card_id"],
            version=values["content_version"], reveal_answer=True)
        saved = learning_service.progress_map([card["card_id"]], user.id).get(card["card_id"])
        if values["expected_revision"] != (saved.revision if saved else 0) or (saved and saved.is_suspended):
            raise learning_service.StaleReviewError()
        return dict(card=card)
    return _concept_call(read)


@learning_api_blueprint.post("/concepts/<concept_id>/rate")
@jwt_required()
def api_rate_concept(concept_id):
    def rate(user):
        concept_progress_service.published_concept(concept_id)
        payload = request.get_json(silent=True)
        required = {"card_id", "content_version", "rating", "expected_revision", "request_id"}
        if (not isinstance(payload, dict) or not required <= set(payload)
                or set(payload) - required - {"response_ms", "session_id"}
                or not isinstance(payload["card_id"], str)
                or payload["card_id"].split(":", 1)[0] != concept_id
                or type(payload["content_version"]) is not int
                or type(payload["expected_revision"]) is not int
                or not isinstance(payload["request_id"], str)):
            raise learning_service.ValidationError("Invalid rating request.")
        return learning_service.rate_card_for_user(user=user,
            notes_dir=learning_service.notes_dir_for_root(current_app.root_path), **payload)
    return _concept_call(rate)


def _concept_progress_response(concept_id, operation):
    user = _current_user_from_jwt()
    if user is None:
        return jsonify(error="Unauthorized."), 401
    try:
        concept_progress_service.published_concept(concept_id)
        if operation == "get":
            saved = concept_progress_service.progress(user.id, concept_id)
        else:
            payload = request.get_json(silent=True)
            required = {"content_version", "section_id", "expected_revision", "request_id"}
            if not isinstance(payload, dict) or set(payload) != (required if operation == "position" else set()):
                raise learning_service.ValidationError("Invalid progress request.")
            saved = (concept_progress_service.enroll(user.id, concept_id) if operation == "enroll" else
                     concept_progress_service.save_position(user.id, concept_id, **payload))
        return jsonify(progress=saved)
    except learning_service.NotFoundError:
        return jsonify(error="Concept not found."), 404
    except learning_service.ValidationError as exc:
        return jsonify(error=str(exc)), 400
    except learning_service.ConflictError as exc:
        return jsonify(error=str(exc)), 409
    except SQLAlchemyError:
        db.session.rollback()
        current_app.logger.exception("Concept progress operation failed")
        return jsonify(error="Progress could not be confirmed. Retry the same request."), 503


@learning_api_blueprint.get("/concepts/<concept_id>/progress")
@jwt_required()
def api_concept_progress(concept_id):
    return _concept_progress_response(concept_id, "get")


@learning_api_blueprint.post("/concepts/<concept_id>/enrollment")
@jwt_required()
def api_enroll_concept(concept_id):
    return _concept_progress_response(concept_id, "enroll")


@learning_api_blueprint.put("/concepts/<concept_id>/reading-position")
@jwt_required()
def api_reading_position(concept_id):
    return _concept_progress_response(concept_id, "position")


@learning_api_blueprint.route("/concepts/<concept_id>/self-assessments", methods=["GET", "POST", "DELETE"])
@jwt_required()
def api_self_assessments(concept_id):
    user = _current_user_from_jwt()
    if user is None:
        return jsonify(error="Unauthorized."), 401
    try:
        if request.method == "GET":
            raw = request.args.get("before")
            if raw is not None and (not raw.isascii() or not raw.isdecimal() or len(raw) > 10):
                raise learning_service.ValidationError("Invalid history cursor.")
            return jsonify(self_assessment_service.history(user.id, concept_id, before=int(raw) if raw is not None else None))
        payload = request.get_json(silent=True)
        keys = {"expected_revision", "request_id"}
        if request.method == "POST":
            keys |= {"content_version", "ratings"}
        if not isinstance(payload, dict) or set(payload) != keys:
            raise learning_service.ValidationError("Invalid self-assessment request.")
        if request.method == "DELETE":
            return jsonify(self_assessment_service.clear_history(user.id, concept_id, **payload))
        return jsonify(checkin=self_assessment_service.save(user.id, concept_id, **payload))
    except learning_service.NotFoundError:
        return jsonify(error="Concept not found."), 404
    except learning_service.ValidationError as exc:
        return jsonify(error=str(exc)), 400
    except self_assessment_service.AssessmentConflict as exc:
        return jsonify(error=str(exc), revision=exc.revision, current=exc.current), 409
    except learning_service.ConflictError as exc:
        return jsonify(error=str(exc)), 409
    except SQLAlchemyError as exc:
        db.session.rollback()
        current_app.logger.warning("Self-assessment operation unconfirmed: %s", type(exc).__name__)
        return jsonify(error="Self-assessment could not be confirmed. Retry the same request."), 503
