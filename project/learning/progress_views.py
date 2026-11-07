"""Small form/JSON adapters for the shared concept progress service."""
from uuid import uuid4

from flask import abort, current_app, jsonify, redirect, render_template, request
from flask_login import current_user
from sqlalchemy.exc import SQLAlchemyError

from project.database import db
from project.services import concept_progress_service as progress_service
from project.services.learning_errors import ConflictError, NotFoundError, ValidationError

from . import learning_blueprint
from .forms import ConceptEnrollmentForm, ReadingPositionForm
from .navigation import selected_session, workspace_navigation


def study_context(concept, workspace):
    saved = progress_service.progress(current_user.id, concept["id"])
    resume = progress_service.resume_section(concept, saved)
    session_id = workspace["session"]["id"] if workspace["session"] else ""
    enrollment = ConceptEnrollmentForm(formdata=None, return_view=workspace["mode"], practice_session=session_id)
    position = ReadingPositionForm(formdata=None, content_version=concept["version"],
        expected_revision=saved["revision"] if saved else 1, request_id=str(uuid4()),
        section_id=resume["id"] if resume else concept["content"]["sections"][0]["id"], practice_session=session_id)
    position.section_id.choices = [(section["id"], section["title"]) for section in concept["content"]["sections"]]
    return dict(concept_progress=saved, resume_section=resume, enrollment_form=enrollment, position_form=position)


def _workspace(concept, mode):
    # An empty hidden field means no explicit selection. Nonempty IDs still go
    # through the existing ownership/matching validation before any write.
    if request.form.get("practice_session") == "":
        return workspace_navigation(concept["id"], mode=mode)
    return workspace_navigation(concept["id"], mode=mode, session=selected_session(concept))


def _error(error, status, *, concept, workspace, form, enrollment=False):
    if request.accept_mimetypes.best == "application/json":
        return jsonify(error=error), status
    return render_template("learning/progress_rescue.html", concept=concept, workspace=workspace,
        error=error, form=form, enrollment=enrollment, conflict=status == 409), status


@learning_blueprint.post("/concepts/<concept_id>/enrollment")
def enroll_concept(concept_id):
    form = ConceptEnrollmentForm()
    if not form.validate_on_submit() or form.return_view.data not in {"learn", "review"}:
        abort(400)
    try:
        concept = progress_service.published_concept(concept_id)
    except NotFoundError:
        abort(404)
    if form.section_id.data and form.section_id.data not in {s["id"] for s in concept["content"]["sections"]}:
        abort(400)
    workspace = _workspace(concept, form.return_view.data)
    try:
        progress_service.enroll(current_user.id, concept_id)
    except SQLAlchemyError:
        db.session.rollback()
        current_app.logger.exception("Concept enrollment could not be confirmed")
        return _error("Your enrollment could not be confirmed. Retry Start learning.", 503,
                      concept=concept, workspace=workspace, form=form, enrollment=True)
    target = workspace[f"{form.return_view.data}_url"]
    if form.return_view.data == "learn" and form.section_id.data:
        target += "#" + form.section_id.data
    return redirect(target, code=303)


@learning_blueprint.post("/concepts/<concept_id>/reading-position")
def save_reading_position(concept_id):
    form = ReadingPositionForm()
    if not form.validate_on_submit():
        abort(400)
    try:
        concept = progress_service.published_concept(concept_id, version=form.content_version.data)
    except NotFoundError:
        abort(404)
    workspace = _workspace(concept, "learn")
    form.section_id.choices = [(s["id"], s["title"]) for s in concept["content"]["sections"]]
    try:
        saved = progress_service.save_position(current_user.id, concept_id, content_version=form.content_version.data,
            section_id=form.section_id.data, expected_revision=form.expected_revision.data, request_id=form.request_id.data)
    except NotFoundError:
        abort(404)
    except (ValidationError, ConflictError) as exc:
        return _error(str(exc), 409 if isinstance(exc, ConflictError) else 400,
                      concept=concept, workspace=workspace, form=form)
    except SQLAlchemyError:
        db.session.rollback()
        current_app.logger.exception("Reading position could not be confirmed")
        return _error("Your reading position could not be confirmed. Retry the same save.", 503,
                      concept=concept, workspace=workspace, form=form)
    if request.accept_mimetypes.best == "application/json":
        return jsonify(progress=saved)
    return redirect(workspace["learn_url"] + "#" + saved["reading_section"], code=303)
