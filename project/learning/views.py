from uuid import uuid4

from flask import abort, current_app, flash, jsonify, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy.exc import SQLAlchemyError

from project.database import db
from project.models import CurriculumItem
from project.services import curriculum_service, learning_service, practice_service

from . import learning_blueprint
from .forms import ConceptRatingForm
from .practice_views import start_form


@learning_blueprint.after_request
def private_study_response(response):
    if current_user.is_authenticated or request.endpoint in {
        "learning.rate_card", "learning.rating_receipt", "learning.review", "learning.note"
    }:
        response.headers["Cache-Control"] = "private, no-store"
    return response


@learning_blueprint.route("/", strict_slashes=False)
def index():
    notes = []
    concepts = []
    practice_sessions = []
    total_due = 0
    if current_user.is_authenticated:
        notes_dir = learning_service.notes_dir_for_root(current_app.root_path)
        notes = learning_service.load_notes(notes_dir)
        notes, total_due = learning_service.summarize_notes_for_user(
            notes,
            user_id=current_user.id,
        )
        concepts = curriculum_service.published_concepts()
        for concept in concepts:
            concept["due_count"] = len(curriculum_service.concept_review_queue(concept, user_id=current_user.id))
        # No practice query at all while the feature is off (e.g. before its migration).
        if practice_service.enabled():
            practice_sessions = practice_service.list_sessions(current_user.id)
    return render_template(
        "learning/index.html",
        notes=notes,
        total_due=total_due,
        concepts=concepts,
        practice_sessions=practice_sessions,
    )


def _published_concept(concept_id):
    concept = curriculum_service.published_learner_item(concept_id)
    if concept is None or concept["kind"] != "concept":
        abort(404)
    return concept


@learning_blueprint.get("/concepts/<concept_id>")
@login_required
def concept(concept_id):
    item = _published_concept(concept_id)
    queue = curriculum_service.concept_review_queue(item, user_id=current_user.id)
    exercises = practice_service.concept_exercises(item, user_id=current_user.id) if practice_service.enabled() else []
    for exercise in exercises:
        exercise["start_form"] = start_form(exercise["id"], item["id"])
    return render_template("learning/concept.html", concept=item, due_count=len(queue), exercises=exercises)


@learning_blueprint.route("/concepts/<concept_id>/review", methods=["GET", "POST"])
@login_required
def concept_review(concept_id):
    item = _published_concept(concept_id)
    notes_dir = learning_service.notes_dir_for_root(current_app.root_path)
    form = ConceptRatingForm()
    error, status, card, revealed = None, 200, None, False
    if request.method == "POST":
        if not form.validate_on_submit():
            abort(400)
        try:
            card = curriculum_service.published_review_question(concept_id, form.card_id.data,
                version=form.content_version.data, notes_dir=notes_dir, reveal_answer=True)
            result = learning_service.rate_card_for_user(user=current_user, notes_dir=notes_dir,
                card_id=card["card_id"], content_version=form.content_version.data, rating=form.rating.data,
                request_id=form.request_id.data, expected_revision=form.expected_revision.data)
        except learning_service.ValidationError:
            abort(400)
        except learning_service.NotFoundError:
            abort(404)
        except learning_service.ConflictError:
            error, status = "This review changed elsewhere. Load the current questions before rating again.", 409
        except SQLAlchemyError:
            db.session.rollback()
            current_app.logger.exception("Concept review save could not be confirmed")
            error, status, revealed = "Your save could not be confirmed. Retry the same rating below.", 503, True
        else:
            flash("Review saved. " + result["next_review_display"], "concept-review")
            return redirect(url_for("learning.concept_review", concept_id=concept_id), code=303)
    elif request.args:
        # A reveal URL pins the original question and progress revision. It does
        # not write progress, even on refresh, back navigation, or link preview.
        try:
            for key in ("content_version", "expected_revision"):
                value = request.args.get(key, "")
                if not value.isascii() or not value.isdecimal() or len(value) > 10:
                    raise ValueError
            version, revision = int(request.args["content_version"]), int(request.args["expected_revision"])
            if not 1 <= version <= 2147483647 or not 0 <= revision <= 2147483647:
                raise ValueError
            attempt = learning_service.validate_request_id(request.args.get("request_id"))
            card = curriculum_service.published_review_question(concept_id, request.args.get("card_id"),
                version=version, notes_dir=notes_dir, reveal_answer=True)
            progress = learning_service.progress_map([card["card_id"]], current_user.id).get(card["card_id"])
            if revision != (progress.revision if progress else 0) or (progress and progress.is_suspended):
                raise learning_service.StaleReviewError()
            form = ConceptRatingForm(card_id=card["card_id"], content_version=version,
                expected_revision=revision, request_id=attempt)
            revealed = True
        except (ValueError, learning_service.ValidationError):
            abort(400)
        except learning_service.NotFoundError:
            abort(404)
        except learning_service.ConflictError:
            error, status = "This review changed elsewhere. Load the current questions before rating again.", 409
    else:
        queue = curriculum_service.concept_review_queue(item, user_id=current_user.id)
        if queue:
            card = queue[0]
            form = ConceptRatingForm(card_id=card["card_id"], content_version=card["content_version"],
                expected_revision=card["progress_revision"], request_id=str(uuid4()))
    return render_template("learning/concept_review.html", concept=item, card=card, form=form,
        revealed=revealed, error=error, retry_same=status == 503, stale=status == 409), status


@learning_blueprint.route(
    "/web-performance/modern-images-video-lazy-loading-responsive-media"
)
def web_performance_media():
    return render_template("learning/web_performance_media.html")


@learning_blueprint.route("/review")
@login_required
def review():
    notes_dir = learning_service.notes_dir_for_root(current_app.root_path)
    notes = learning_service.load_notes(notes_dir)
    due_cards = learning_service.review_cards_for_user(
        notes,
        user_id=current_user.id,
    )

    return render_template(
        "learning/review.html",
        cards=due_cards,
    )


@learning_blueprint.route("/note/<note_id>")
@login_required
def note(note_id):
    notes_dir = learning_service.notes_dir_for_root(current_app.root_path)
    try:
        note_data = learning_service.note_with_cards(notes_dir, note_id, user_id=current_user.id)
    except learning_service.NotFoundError:
        abort(404)
    return render_template("learning/note.html", note=note_data)


@learning_blueprint.route("/rate", methods=["POST"])
@login_required
def rate_card():
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
            user=current_user,
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
        }), 409
    except learning_service.ConflictError:
        return jsonify({
            "error": "This request ID was already used for a different rating.",
        }), 409
    return jsonify(response_data)


@learning_blueprint.route("/ratings/<request_id>")
@login_required
def rating_receipt(request_id):
    try:
        receipt = learning_service.rating_receipt(current_user, request_id)
    except learning_service.ValidationError:
        return jsonify({"error": "Invalid request ID."}), 400
    return jsonify({"receipt": receipt})


@learning_blueprint.route("/api/incident", methods=["POST"])
@login_required
def create_incident():
    if not current_user.is_admin:
        return jsonify({"error": "admin access required"}), 403

    payload = request.get_json(silent=True) or {}
    note_id = payload.get("note_id")
    title = payload.get("title")
    symptom = payload.get("symptom")
    root_cause = payload.get("root_cause")
    fix = payload.get("fix")
    prevention = payload.get("prevention", "")
    tags = payload.get("tags", [])
    notes_dir = learning_service.notes_dir_for_root(current_app.root_path)
    # The legacy authoring endpoint must not reuse a curriculum review namespace.
    candidate = note_id or learning_service.slugify(title or "")
    if isinstance(candidate, str) and db.session.get(CurriculumItem, candidate) is not None:
        return jsonify({"error": "This ID belongs to a curriculum concept."}), 409
    try:
        resolved_note_id, card_id = learning_service.create_incident_card(
            notes_dir=notes_dir,
            note_id=note_id,
            title=title,
            symptom=symptom,
            root_cause=root_cause,
            fix=fix,
            prevention=prevention,
            tags=tags,
            desired_card_id=payload.get("id"),
        )
    except learning_service.ConflictError:
        return jsonify({"error": "card id already exists"}), 400
    except learning_service.ValidationError:
        return jsonify({"error": "Invalid incident data."}), 400
    return jsonify({"note_id": resolved_note_id, "card_id": card_id}), 201
