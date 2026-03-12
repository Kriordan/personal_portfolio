from flask import abort, current_app, jsonify, render_template, request
from flask_login import current_user, login_required

from project.services import learning_service

from . import learning_blueprint

@learning_blueprint.route("/")
@login_required
def index():
    notes_dir = learning_service.notes_dir_for_root(current_app.root_path)
    notes = learning_service.load_notes(notes_dir)
    notes, total_due = learning_service.summarize_notes_for_user(
        notes,
        user_id=current_user.id,
    )
    return render_template(
        "learning/index.html",
        notes=notes,
        total_due=total_due,
    )


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
        note_data = learning_service.note_with_cards(notes_dir, note_id)
    except learning_service.NotFoundError:
        abort(404)
    return render_template("learning/note.html", note=note_data)


@learning_blueprint.route("/rate", methods=["POST"])
@login_required
def rate_card():
    payload = request.get_json(silent=True) or {}
    card_id = payload.get("card_id")
    rating = payload.get("rating")
    response_ms = payload.get("response_ms")
    session_id = payload.get("session_id")

    if not card_id or rating is None:
        return jsonify({"error": "card_id and rating are required"}), 400

    try:
        rating = int(rating)
    except (TypeError, ValueError):
        return jsonify({"error": "rating must be an integer"}), 400

    notes_dir = learning_service.notes_dir_for_root(current_app.root_path)
    try:
        response_data = learning_service.rate_card_for_user(
            user=current_user,
            notes_dir=notes_dir,
            card_id=card_id,
            rating=rating,
            response_ms=response_ms,
            session_id=session_id,
        )
    except learning_service.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    except learning_service.NotFoundError as exc:
        return jsonify({"error": str(exc)}), 404
    return jsonify(response_data)


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
    except learning_service.ConflictError as exc:
        return jsonify({"error": str(exc)}), 400
    except learning_service.ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify({"note_id": resolved_note_id, "card_id": card_id}), 201
