"""Optional native reflection forms, with no calls to AI or study scheduling."""
from uuid import uuid4

from flask import abort, current_app, flash, redirect, render_template, request, url_for
from flask_login import current_user
from sqlalchemy.exc import SQLAlchemyError

from project.database import db
from project.services import self_assessment_service as assessment, practice_service
from project.services.learning_errors import ConflictError, NotFoundError, ValidationError
from . import learning_blueprint
from .forms import ClearSelfAssessmentForm, SelfAssessmentForm
from .navigation import selected_session, workspace_navigation
from .self_assessment import DIMENSIONS, RATINGS


def _url(concept_id, session_id="", *, delete=False, **kwargs):
    return url_for("learning.clear_self_assessment" if delete else "learning.concept_self_assessment",
        concept_id=concept_id, practice_session=session_id or None, **kwargs)


def _selected(concept_id, concept=None):
    session_id = request.form.get("practice_session", "") if request.method == "POST" else request.args.get("practice_session", "")
    if session_id:
        session = practice_service.session_summary(current_user.id, session_id)
        if session["concept_id"] != concept_id:
            raise NotFoundError("Practice session not found.")
        return session
    return selected_session(concept) if concept and request.method == "GET" else None


def _rescue(concept_id, form, message, status, *, delete=False, latest=None, can_retry=True, compare=False):
    # Standalone template: no layout or DB reads after a possibly committed write.
    return render_template("learning/self_assessment_rescue.html", form=form, message=message,
        dimensions=DIMENSIONS, rating_labels=dict(RATINGS), latest=latest, delete=delete,
        can_retry=can_retry, compare=compare, action_url=_url(concept_id, delete=delete),
        back_url=_url(concept_id, form.practice_session.data),
        confirmation_url=_url(concept_id, form.practice_session.data, delete=True)), status


def _write(concept_id, *, delete=False):
    form = ClearSelfAssessmentForm() if delete else SelfAssessmentForm()
    if not form.validate_on_submit():
        return _rescue(concept_id, form, "Nothing was saved. Check the form and try again.", 400, delete=delete)
    try:
        _selected(concept_id)  # Authorize explicit session context before any mutation.
        payload = dict(expected_revision=form.expected_revision.data, request_id=form.request_id.data)
        if delete:
            assessment.clear_history(current_user.id, concept_id, **payload)
        else:
            assessment.save(current_user.id, concept_id, **payload, content_version=form.content_version.data,
                ratings={key: form[key].data for key, _, _ in DIMENSIONS})
    except NotFoundError:
        abort(404)
    except assessment.AssessmentConflict as exc:
        if delete:
            return _rescue(concept_id, form, "Your check-ins changed elsewhere. Review the latest history before deleting it.",
                409, delete=True, can_retry=False)
        # Rebuild, rather than changing IntegerField.data: WTForms prefers raw_data.
        form = SelfAssessmentForm(formdata=None, data={**form.data,
            "expected_revision": exc.revision, "request_id": str(uuid4())})
        return _rescue(concept_id, form, "A newer change was saved elsewhere. Your choices are below; compare them before saving a new check-in.",
            409, latest=exc.current, compare=True)
    except ConflictError:
        return _rescue(concept_id, form, "This request belongs to another change or a deleted check-in. Your choices are still here. Open your latest history before making another change.",
            409, delete=delete, can_retry=False)
    except ValidationError as exc:
        return _rescue(concept_id, form, str(exc), 400, delete=delete)
    except SQLAlchemyError as exc:
        db.session.rollback()
        current_app.logger.warning("Self-assessment write unconfirmed: %s", type(exc).__name__)
        message = ("Deletion was not confirmed. Retry this same request safely; check-ins saved afterward will be kept." if delete else
                   "The save was not confirmed. Retry this same request safely; an earlier save will not be duplicated.")
        return _rescue(concept_id, form, message, 503, delete=delete)
    flash("Deletion confirmed. Any check-ins saved afterward are kept." if delete else "Check-in saved.", "self-assessment")
    return redirect(_url(concept_id, form.practice_session.data), code=303)


@learning_blueprint.route("/concepts/<concept_id>/self-assessment", methods=["GET", "POST"])
def concept_self_assessment(concept_id):
    if request.method == "POST":
        return _write(concept_id)
    try:
        concept = assessment.concept_for_reader(current_user.id, concept_id)
        raw = request.args.get("before")
        if raw is not None and (not raw.isascii() or not raw.isdecimal() or len(raw) > 10):
            raise ValidationError("Invalid history cursor.")
        saved = assessment.history(current_user.id, concept_id, before=int(raw) if raw is not None else None)
        selected = _selected(concept_id, concept)
    except NotFoundError:
        abort(404)
    except ValidationError:
        abort(400)
    workspace = workspace_navigation(concept_id, mode="self-assessment", session=selected)
    session_id = selected["id"] if selected else ""
    form = SelfAssessmentForm(formdata=None, data={
        **(saved["current"]["ratings"] if saved["current"] else {}),
        "expected_revision": saved["revision"], "request_id": str(uuid4()),
        "content_version": concept["version"] if concept else None, "practice_session": session_id})
    return render_template("learning/self_assessment.html", workspace=workspace, form=form, saved=saved,
        available=concept is not None, dimensions=DIMENSIONS, rating_labels=dict(RATINGS), older_page=raw is not None,
        action_url=_url(concept_id), latest_url=_url(concept_id, session_id, _anchor="assessment-history"),
        older_url=_url(concept_id, session_id, before=saved["next_before"], _anchor="assessment-history"),
        delete_url=_url(concept_id, session_id, delete=True))


@learning_blueprint.route("/concepts/<concept_id>/self-assessment/delete", methods=["GET", "POST"])
def clear_self_assessment(concept_id):
    if request.method == "POST":
        return _write(concept_id, delete=True)
    try:
        concept = assessment.concept_for_reader(current_user.id, concept_id)
        saved = assessment.history(current_user.id, concept_id)
        selected = _selected(concept_id, concept)
    except NotFoundError:
        abort(404)
    workspace = workspace_navigation(concept_id, mode="self-assessment", session=selected)
    session_id = selected["id"] if selected else ""
    form = ClearSelfAssessmentForm(formdata=None, expected_revision=saved["revision"],
        request_id=str(uuid4()), practice_session=session_id)
    return render_template("learning/self_assessment_delete.html", workspace=workspace, form=form,
        action_url=_url(concept_id, delete=True), back_url=_url(concept_id, session_id))
