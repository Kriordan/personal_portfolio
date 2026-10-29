"""Practice workspace routes.

A rejected or failed save always re-renders the learner's submitted text. If the
database is unavailable, a standalone page that needs no database or shared layout
holds the text for a retry. Logs carry failure summaries, never learner text.
"""
from datetime import datetime
from uuid import uuid4

from flask import abort, current_app, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy.exc import OperationalError, SQLAlchemyError

from project.database import db
from project.services import learning_service, practice_service as practice

from . import learning_blueprint
from .forms import LANGUAGE_LABELS, PracticeWorkspaceForm, StartPracticeForm

PRACTICE_REQUEST_BYTES = 2 * 1024 * 1024
STATUS_LABELS = {"active": "In progress", "paused": "Paused", "completed": "Completed"}


@learning_blueprint.before_request
def guard_practice_routes():
    if not (request.endpoint or "").startswith("learning.practice_"):
        return None
    if not practice.enabled():
        abort(404)
    request.max_content_length = PRACTICE_REQUEST_BYTES
    return None


@learning_blueprint.app_template_filter("practice_time")
def practice_time(value):
    return datetime.fromisoformat(value).strftime("%b %d, %Y, %H:%M UTC") if value else ""


def start_form(exercise_id, concept_id):
    return StartPracticeForm(formdata=None, data={"exercise_id": exercise_id, "concept_id": concept_id,
                                                  "request_id": str(uuid4())})


@learning_blueprint.post("/practice")
@login_required
def practice_start():
    form = StartPracticeForm()
    if not form.validate_on_submit():
        abort(400)
    try:
        result = practice.start_session(current_user, exercise_id=form.exercise_id.data,
                                        concept_id=form.concept_id.data, request_id=form.request_id.data)
    except learning_service.NotFoundError:
        abort(404)
    except learning_service.ConflictError:
        abort(409)
    except learning_service.ValidationError:
        abort(400)
    except SQLAlchemyError as exc:
        db.session.rollback()
        current_app.logger.error("Practice session could not be started: %s", practice.describe_failure(exc))
        abort(503)
    return redirect(url_for("learning.practice_workspace", session_id=result["session_id"]), code=303)


def _workspace_form(detail, *, values=None, request_id=None):
    """Editors filled from saved heads, with optional per-artifact overrides."""
    entries = []
    for artifact in detail["artifacts"]:
        entry = {"artifact_id": artifact["artifact_id"], "base_revision": artifact["revision"],
                 "language": artifact["language"], "body": artifact["body"]}
        entry.update((values or {}).get(artifact["artifact_id"], {}))
        entries.append(entry)
    form = PracticeWorkspaceForm(formdata=None, data={"request_id": request_id or str(uuid4()), "artifacts": entries})
    for entry, artifact in zip(form.artifacts, detail["artifacts"]):
        entry.form.language.choices = [(name, LANGUAGE_LABELS[name]) for name in artifact["languages"]]
    return form


def _render(detail, form, *, status=200, alert=None, errors=None, conflicts=(), unsaved=False):
    return render_template(
        "learning/practice.html", detail=detail, form=form, alert=alert, errors=errors or {},
        artifacts={artifact["artifact_id"]: artifact for artifact in detail["artifacts"]},
        conflicts={conflict["artifact_id"]: conflict for conflict in conflicts}, unsaved=unsaved,
        status_label=STATUS_LABELS[detail["session"]["status"]], limit=practice.ARTIFACT_MAX_BYTES,
        language_labels=LANGUAGE_LABELS,
    ), status


def _submitted(form):
    return [{"artifact_id": entry.form.artifact_id.data, "base_revision": entry.form.base_revision.data,
             "language": entry.form.language.data, "body": entry.form.body.data or ""}
            for entry in form.artifacts]


def _rescue(session_id, edits, *, request_id, exc):
    """Hold the learner's text without touching the database or the shared layout."""
    db.session.rollback()
    current_app.logger.error("Practice save could not be confirmed: %s", practice.describe_failure(exc))
    form = PracticeWorkspaceForm(formdata=None, data={"request_id": request_id, "artifacts": [
        {key: edit[key] for key in ("artifact_id", "base_revision", "language", "body")} for edit in edits]})
    return render_template("learning/practice_rescue.html", session_id=session_id, form=form), 503


def _rerender(session_id, edits, *, status, alert, errors=None, conflicts=(), refresh=()):
    """Show the submitted text again, beside anything that changed elsewhere."""
    try:
        detail = practice.session_detail(current_user.id, session_id)
    except learning_service.NotFoundError:
        abort(404)
    except SQLAlchemyError as exc:
        return _rescue(session_id, edits, request_id=str(uuid4()), exc=exc)
    values = {}
    for edit in edits:
        if isinstance(edit["artifact_id"], str):
            value = {"body": edit["body"], "language": edit["language"]}
            if type(edit["base_revision"]) is int:
                value["base_revision"] = edit["base_revision"]
            values[edit["artifact_id"]] = value
    for conflict in conflicts:
        # Saving again is an informed choice to put this text on top of the newer revision.
        values.setdefault(conflict["artifact_id"], {})["base_revision"] = conflict["revision"]
    for current in refresh:
        values[current["artifact_id"]] = {"body": current["body"], "language": current["language"],
                                          "base_revision": current["revision"]}
    return _render(detail, _workspace_form(detail, values=values), status=status, alert=alert,
                   errors=errors, conflicts=conflicts, unsaved=True)


def _save(session_id):
    form = PracticeWorkspaceForm()
    edits = _submitted(form)
    if not form.validate_on_submit():
        alert = ("This page was open too long to save safely. Your text is still here: press Save work again."
                 if "csrf_token" in form.errors else "Nothing was saved. Your text is still here: press Save work again.")
        return _rerender(session_id, edits, status=400, alert=alert)
    try:
        result = practice.save_artifacts(current_user, session_id, edits=edits, request_id=form.request_id.data)
    except learning_service.NotFoundError:
        abort(404)
    except practice.PracticeValidationError as exc:
        return _rerender(session_id, edits, status=400, alert="Nothing was saved. " + exc.message,
                         errors={exc.field: exc.message} if exc.field else None)
    except practice.StaleArtifactError as exc:
        return _rerender(session_id, edits, status=409, conflicts=exc.conflicts, refresh=exc.refresh,
                         alert="Nothing was saved: newer work was saved from another tab or device. "
                               "Compare each marked artifact, then save again.")
    except practice.RequestConflictError:
        return _rerender(session_id, edits, status=409,
                         alert="An earlier attempt from this page may already have saved. "
                               "Check the saved revisions, then save again.")
    except learning_service.ValidationError:
        return _rerender(session_id, edits, status=400, alert="Nothing was saved. Press Save work again.")
    except OperationalError as exc:
        # The outcome is unknown: retrying the same request ID either saves or replays.
        return _rescue(session_id, edits, request_id=form.request_id.data, exc=exc)
    except SQLAlchemyError as exc:
        return _rescue(session_id, edits, request_id=str(uuid4()), exc=exc)
    changed = sum(outcome["changed"] for outcome in result["artifacts"].values())
    flash(f"Saved {changed} artifact{'s' if changed != 1 else ''}." if changed
          else "No changes to save: everything matches the saved versions.", "practice")
    return redirect(url_for("learning.practice_workspace", session_id=session_id), code=303)


@learning_blueprint.route("/practice/<session_id>", methods=["GET", "POST"])
@login_required
def practice_workspace(session_id):
    if request.method == "POST":
        return _save(session_id)
    try:
        detail = practice.session_detail(current_user.id, session_id)
    except learning_service.NotFoundError:
        abort(404)
    return _render(detail, _workspace_form(detail))


def _history(session_id, artifact_id, revision=None):
    try:
        history = practice.artifact_history(current_user.id, session_id, artifact_id)
        selected = (practice.artifact_revision(current_user.id, session_id, artifact_id, revision)
                    if revision is not None else None)
    except learning_service.NotFoundError:
        abort(404)
    return render_template("learning/practice_history.html", history=history, selected=selected,
                           language_labels=LANGUAGE_LABELS)


@learning_blueprint.get("/practice/<session_id>/artifacts/<artifact_id>")
@login_required
def practice_history(session_id, artifact_id):
    return _history(session_id, artifact_id)


@learning_blueprint.get("/practice/<session_id>/artifacts/<artifact_id>/<int:revision>")
@login_required
def practice_revision(session_id, artifact_id, revision):
    return _history(session_id, artifact_id, revision)
