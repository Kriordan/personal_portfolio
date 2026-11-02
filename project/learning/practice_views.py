"""Practice workspace routes.

The workspace is one form holding the artifacts, the learner's brief, and a message
box. Save, Send, Save and pause, and Resume all submit all of it, so no button discards
anything else on the page. A rejected or failed request always re-renders the learner's
submitted text. If the database is unavailable, a standalone page that needs no database
or shared layout holds the text for a retry. Logs carry failure summaries, never
learner text.
"""
import json
from datetime import datetime
from uuid import uuid4

from flask import abort, current_app, flash, jsonify, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy.exc import OperationalError, SQLAlchemyError

from project.database import db
from project.services import learning_service, practice_service as practice

from . import learning_blueprint
from .forms import BRIEF_TYPE_LABELS, LANGUAGE_LABELS, DeletePracticeForm, PracticeWorkspaceForm, StartPracticeForm
from .navigation import workspace_navigation

PRACTICE_REQUEST_BYTES = 2 * 1024 * 1024
STATUS_LABELS = {"active": "In progress", "paused": "Paused", "completed": "Completed"}
ACTIONS = ("save", "send", "pause", "resume", "reply", "recent", "submit")
LIVE = ("pending", "running")
BLANK_BRIEF_ROWS = 3


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
    view = request.args.get("view")
    if view is not None and view not in {"discuss", "build"}:
        abort(400)
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
    return redirect(url_for("learning.practice_workspace", session_id=result["session_id"],
                            **({"view": view} if view else {})), code=303)


def _saved_rows(entries):
    """Form rows for saved brief entries. Sources round-trip as compact JSON."""
    return [{"entry_id": entry["id"], "kind": entry["type"], "text": entry["text"], "pinned": entry["pinned"],
             "remove": False, "sources": json.dumps(entry["sources"], separators=(",", ":")) if entry["sources"] else ""}
            for entry in entries]


def _with_blank_rows(rows):
    blanks = min(BLANK_BRIEF_ROWS, practice.BRIEF_MAX_ENTRIES - len(rows))
    return rows + [{"entry_id": uuid4().hex[:12], "kind": "assumption", "text": "", "pinned": False, "remove": False,
                    "sources": ""} for _ in range(max(blanks, 0))]


def _parse_sources(value):
    if not value:
        return []
    try:
        return json.loads(value)
    except ValueError:
        return value  # the service rejects anything that isn't a list of sources


def _shown_sources(value):
    """Sources to describe beside an entry; anything malformed is left for the service to reject."""
    sources = _parse_sources(value)
    if not isinstance(sources, list):
        return []
    return [source for source in sources if isinstance(source, dict) and (
        type(source.get("turn")) is int or (isinstance(source.get("artifact_id"), str)
                                            and type(source.get("revision")) is int))]


def _workspace_form(detail, *, artifacts=None, brief=None, message="", expected_sequence=None, request_id=None):
    """The form for the saved state, with optional overrides from a submission.

    `artifacts` maps artifact IDs to field overrides; `brief` is {"base_revision", "rows"}.
    """
    entries = []
    for artifact in detail["artifacts"]:
        entry = {"artifact_id": artifact["artifact_id"], "base_revision": artifact["revision"],
                 "language": artifact["language"], "body": artifact["body"]}
        entry.update((artifacts or {}).get(artifact["artifact_id"], {}))
        entries.append(entry)
    if brief is None:
        saved = detail["session_brief"]
        brief = {"base_revision": saved["revision"], "rows": _with_blank_rows(_saved_rows(saved["entries"]))}
    if expected_sequence is None:
        expected_sequence = detail["messages"][-1]["sequence"] if detail["messages"] else 0
    form = PracticeWorkspaceForm(formdata=None, data={
        "request_id": request_id or str(uuid4()), "expected_sequence": expected_sequence,
        "brief_revision": brief["base_revision"], "artifacts": entries, "brief": brief["rows"], "message": message})
    for entry, artifact in zip(form.artifacts, detail["artifacts"]):
        entry.form.language.choices = [(name, LANGUAGE_LABELS[name]) for name in artifact["languages"]]
    return form


def _money(microusd):
    return f"${microusd / 1_000_000:,.2f}"


def _render(detail, form, *, status=200, alert=None, notice=None, errors=None, stale=None, refreshed=(),
            brief_refreshed=False, new_after=None, unsaved=False):
    return render_template(
        "learning/practice.html", detail=detail, form=form, alert=alert, notice=notice, errors=errors or {},
        workspace=workspace_navigation(detail["session"]["concept_id"], mode="practice", session=detail["session"]),
        artifacts={artifact["artifact_id"]: artifact for artifact in detail["artifacts"]},
        titles={artifact["artifact_id"]: artifact["title"] for artifact in detail["artifacts"]},
        reply_live=detail["reply"]["status"] in LIVE, money=_money,
        conflicts={conflict["artifact_id"]: conflict for conflict in (stale.conflicts if stale else [])},
        refreshed=set(refreshed) | {current["artifact_id"] for current in (stale.refresh if stale else [])},
        brief_conflict=stale.brief_conflict if stale else None,
        brief_refreshed=brief_refreshed or (stale is not None and stale.brief_refresh is not None),
        new_after=new_after, unsaved=unsaved,
        sources={row.entry_id.data: _shown_sources(row.sources.data) for row in form.brief},
        status_label=STATUS_LABELS[detail["session"]["status"]], paused=detail["session"]["status"] == "paused",
        limits={"artifact": practice.ARTIFACT_MAX_BYTES, "turn": practice.TURN_MAX_BYTES},
        language_labels=LANGUAGE_LABELS, type_labels=BRIEF_TYPE_LABELS,
    ), status


def _submitted(form):
    """Everything the learner sent, kept for any re-render."""
    return {
        "edits": [{"artifact_id": entry.form.artifact_id.data, "base_revision": entry.form.base_revision.data,
                   "language": entry.form.language.data, "body": entry.form.body.data or ""}
                  for entry in form.artifacts],
        "rows": [{"entry_id": row.form.entry_id.data or "", "kind": row.form.kind.data or "",
                  "text": row.form.text.data or "", "pinned": bool(row.form.pinned.data),
                  "remove": bool(row.form.remove.data), "sources": row.form.sources.data or ""}
                 for row in form.brief],
        "message": form.message.data or "",
        "expected_sequence": form.expected_sequence.data,
        "brief_revision": form.brief_revision.data,
    }


def _entries(rows):
    """Brief entries from form rows: those with text that aren't marked for removal, in page order."""
    return [{"id": row["entry_id"], "type": row["kind"], "text": row["text"], "pinned": row["pinned"],
             "sources": _parse_sources(row["sources"])}
            for row in rows if not row["remove"] and row["text"].strip()]


def _brief(submitted):
    return {"base_revision": submitted["brief_revision"], "entries": _entries(submitted["rows"])}


def _match_saved(detail, artifacts, brief):
    """Base any submitted part that already equals the saved head on that head.

    After a save whose response was lost, the page still names the older revision; a
    later edit would otherwise conflict with the learner's own saved work.
    """
    for artifact in detail["artifacts"]:
        value = artifacts.get(artifact["artifact_id"])
        if (value is not None and value.get("language") == artifact["language"]
                and practice.same_text(value.get("body"), artifact["body"])):
            value["base_revision"] = artifact["revision"]
    saved = detail["session_brief"]
    if practice.same_brief(_entries(brief["rows"]), saved["entries"]):
        brief["base_revision"] = saved["revision"]


def _newer_while_writing(submitted, result, detail):
    """What a save left in place that changed elsewhere since the page loaded, and any newer turns."""
    bases = {edit["artifact_id"]: edit for edit in submitted["edits"] if isinstance(edit["artifact_id"], str)}
    heads = {artifact["artifact_id"]: artifact for artifact in detail["artifacts"]}
    refreshed = set()
    for artifact_id, outcome in result.get("artifacts", {}).items():
        edit, head = bases.get(artifact_id), heads.get(artifact_id)
        if (edit is not None and head is not None and not outcome["changed"]
                and type(edit["base_revision"]) is int and outcome["revision"] > edit["base_revision"]
                and not practice.same_text(edit["body"], head["body"])):
            refreshed.add(artifact_id)
    brief, base = result.get("brief"), submitted["brief_revision"]
    brief_refreshed = bool(brief and not brief["changed"] and type(base) is int and brief["revision"] > base
                           and not practice.same_brief(_entries(submitted["rows"]), detail["session_brief"]["entries"]))
    expected = submitted["expected_sequence"]
    latest = detail["messages"][-1]["sequence"] if detail["messages"] else 0
    new_after = expected if type(expected) is int and latest > expected else None
    return refreshed, brief_refreshed, new_after


def _errors(exc):
    """Where a validation message belongs: beside an artifact, the brief, or the message box."""
    if exc.part == "artifact" and exc.field:
        return {"artifacts": {exc.field: exc.message}}
    if exc.part == "brief":
        return {"brief": exc.message, "brief_entry": exc.field}
    if exc.part == "turn":
        return {"message": exc.message}
    return {}


def _rescue(session_id, submitted, *, action, request_id, exc):
    """Hold the learner's work without touching the database or the shared layout."""
    db.session.rollback()
    current_app.logger.error("Practice request could not be confirmed: %s", practice.describe_failure(exc))
    form = PracticeWorkspaceForm(formdata=None, data={
        "request_id": request_id, "expected_sequence": submitted["expected_sequence"],
        "brief_revision": submitted["brief_revision"], "artifacts": submitted["edits"], "brief": submitted["rows"],
        "message": submitted["message"]})
    return render_template("learning/practice_rescue.html", session_id=session_id, form=form, action=action,
                           type_labels=BRIEF_TYPE_LABELS), 503


def _rerender(session_id, submitted, *, action, status, alert, errors=None, stale=None):
    """Show the submitted work again, beside anything that changed elsewhere."""
    try:
        detail = practice.session_detail(current_user.id, session_id)
    except learning_service.NotFoundError:
        abort(404)
    except SQLAlchemyError as exc:
        return _rescue(session_id, submitted, action=action, request_id=str(uuid4()), exc=exc)
    artifacts = {}
    for edit in submitted["edits"]:
        if isinstance(edit["artifact_id"], str):
            value = {"body": edit["body"], "language": edit["language"]}
            if type(edit["base_revision"]) is int:
                value["base_revision"] = edit["base_revision"]
            artifacts[edit["artifact_id"]] = value
    base = submitted["brief_revision"]
    brief = {"base_revision": detail["session_brief"]["revision"] if base is None else base, "rows": submitted["rows"]}
    expected, new_after = submitted["expected_sequence"], None
    if stale is not None:
        # Saving again after seeing the newer work is an informed choice: advance only what is stale.
        for conflict in stale.conflicts:
            artifacts.setdefault(conflict["artifact_id"], {})["base_revision"] = conflict["revision"]
        for current in stale.refresh:
            artifacts[current["artifact_id"]] = {"body": current["body"], "language": current["language"],
                                                 "base_revision": current["revision"]}
        if stale.brief_conflict is not None:
            brief["base_revision"] = stale.brief_conflict["revision"]
        if stale.brief_refresh is not None:
            brief = {"base_revision": stale.brief_refresh["revision"],
                     "rows": _with_blank_rows(_saved_rows(stale.brief_refresh["entries"]))}
        if stale.latest_turn is not None:
            new_after, expected = expected, stale.latest_turn
    _match_saved(detail, artifacts, brief)
    form = _workspace_form(detail, artifacts=artifacts, brief=brief, message=submitted["message"],
                           expected_sequence=expected)
    return _render(detail, form, status=status, alert=alert, errors=errors, stale=stale, new_after=new_after,
                   unsaved=True)


def _stale_alert(stale, action):
    if action == "submit":
        return ("No snapshot was saved: this page was out of date. Compare the marked work and latest messages, "
                "then save and check again. Your message has not been sent.")
    if stale.conflicts or stale.brief_conflict is not None:
        verb, again = ("sent", "send") if action == "send" else ("saved", "save")
        return (f"Nothing was {verb}: newer work was saved from another tab or device. "
                f"Compare each marked part, then {again} again.")
    return ("Nothing was sent: this page was out of date. It now shows the latest work and messages, and your "
            "message is still in the box. Check them, then send again.")


def _summary(result, action):
    changed = sum(outcome["changed"] for outcome in result.get("artifacts", {}).values())
    brief = result.get("brief", {}).get("changed", False)
    noun = f"{changed} artifact{'s' if changed != 1 else ''}"
    parts = ["Message sent."] if action == "send" else []
    if action == "submit":
        parts.append("Snapshot saved with syntax check results. You can keep editing.")
    if "context_from_sequence" in result:
        parts.append("The interviewer now reads from a recent message on, marked in the conversation. "
                     "Nothing was deleted.")
    if action in ("reply", "recent"):
        parts.append({"pending": "Asked the interviewer for a reply.",
                      "answered": "The interviewer has already replied."}.get(
            result["reply"]["status"], "The interviewer can't reply right now."))
    if changed and brief:
        parts.append(f"Saved {noun} and your brief.")
    elif changed:
        parts.append(f"Saved {noun}.")
    elif brief:
        parts.append("Saved your brief.")
    if action == "pause":
        parts.append("Session paused: resume it from Learning on any device.")
    elif action == "resume":
        parts.append("Session resumed.")
    return " ".join(parts) or "No changes to save: everything matches the saved versions."


def _post(session_id):
    form = PracticeWorkspaceForm()
    submitted = _submitted(form)
    action = request.form.get("action", "save")
    if action not in ACTIONS:
        action = "save"
    verb, again = ("sent", "send again") if action == "send" else ("saved", "try again")
    if not form.validate_on_submit():
        alert = (f"This page was open too long to save safely. Your work is still here: {again}."
                 if "csrf_token" in form.errors else f"Nothing was {verb}. Your work is still here: {again}.")
        return _rerender(session_id, submitted, action=action, status=400, alert=alert)
    request_id = form.request_id.data
    try:
        if action == "send":
            result = practice.save_and_send(current_user, session_id, edits=submitted["edits"], brief=_brief(submitted),
                                            body=submitted["message"], expected_sequence=submitted["expected_sequence"],
                                            request_id=request_id)
        elif action == "submit":
            result = practice.save_and_submit(current_user, session_id, edits=submitted["edits"],
                                              brief=_brief(submitted), expected_sequence=submitted["expected_sequence"],
                                              request_id=request_id)
        elif action in ("reply", "recent"):
            result = practice.request_reply(current_user, session_id, edits=submitted["edits"], brief=_brief(submitted),
                                            context="recent" if action == "recent" else None, request_id=request_id)
        else:
            result = practice.save_work(current_user, session_id, edits=submitted["edits"], brief=_brief(submitted),
                                        request_id=request_id, status="paused" if action == "pause" else "active")
    except learning_service.NotFoundError:
        abort(404)
    except practice.PracticeValidationError as exc:
        return _rerender(session_id, submitted, action=action, status=400, alert=f"Nothing was {verb}. {exc.message}",
                         errors=_errors(exc))
    except practice.StaleViewError as exc:
        return _rerender(session_id, submitted, action=action, status=409, alert=_stale_alert(exc, action), stale=exc)
    except practice.RequestConflictError:
        return _rerender(session_id, submitted, action=action, status=409,
                         alert="An earlier attempt from this page may already have saved. "
                               "Check the saved work, then try again.")
    except practice.ReplyPendingError:
        return _rerender(session_id, submitted, action=action, status=409,
                         alert="The interviewer is still replying. Your work is still here: "
                               "try again once the reply arrives.")
    except learning_service.ValidationError:
        return _rerender(session_id, submitted, action=action, status=400, alert=f"Nothing was {verb}: {again}.")
    except OperationalError as exc:
        # The outcome is unknown: retrying the same request ID either saves or replays.
        return _rescue(session_id, submitted, action=action, request_id=request_id, exc=exc)
    except SQLAlchemyError as exc:
        return _rescue(session_id, submitted, action=action, request_id=str(uuid4()), exc=exc)
    summary = _summary(result, action)
    if action != "send" and submitted["message"].strip():
        # A redirect would drop the unsent message, so show the saved page with it still in the box.
        try:
            detail = practice.session_detail(current_user.id, session_id)
        except learning_service.NotFoundError:
            abort(404)
        except SQLAlchemyError as exc:
            return _rescue(session_id, submitted, action=action, request_id=request_id, exc=exc)
        form = _workspace_form(detail, message=submitted["message"])
        refreshed, brief_refreshed, new_after = _newer_while_writing(submitted, result, detail)
        if refreshed or brief_refreshed or new_after is not None:
            # The message was written against an older view. Say so, as an out-of-date Send would,
            # before the page moves on to the latest state.
            saved = (any(outcome["changed"] for outcome in result.get("artifacts", {}).values())
                     or result.get("brief", {}).get("changed", False) or action in ("pause", "resume", "reply", "recent", "submit"))
            return _render(detail, form, alert=(f"{summary} " if saved else "") + "Newer work arrived while you were "
                           "writing and is marked below. Your message hasn't been sent.",
                           refreshed=refreshed, brief_refreshed=brief_refreshed, new_after=new_after)
        return _render(detail, form, notice=f"{summary} Your message hasn't been sent.")
    flash(summary, "practice")
    if action == "submit":
        return redirect(url_for("learning.practice_workspace", session_id=session_id, view="build",
                                work="work-checks", _anchor="work-checks"), code=303)
    return redirect(url_for("learning.practice_workspace", session_id=session_id), code=303)


@learning_blueprint.route("/practice/<session_id>", methods=["GET", "POST"])
@login_required
def practice_workspace(session_id):
    if request.method == "POST":
        return _post(session_id)
    try:
        detail = practice.session_detail(current_user.id, session_id)
    except learning_service.NotFoundError:
        abort(404)
    return _render(detail, _workspace_form(detail))


@learning_blueprint.get("/practice/<session_id>/reply")
@login_required
def practice_reply(session_id):
    """Polled by the workspace while a reply is on its way: the reply's state and every newer turn."""
    raw = request.args.get("after", "")
    if not (raw.isascii() and raw.isdigit()):
        return jsonify(error="Send after=<sequence>."), 400
    try:
        updates = practice.reply_updates(current_user.id, session_id, after=int(raw))
        titles = ({artifact["artifact_id"]: artifact["title"]
                   for artifact in practice.session_detail(current_user.id, session_id)["artifacts"]}
                  if updates["turns"] else {})
    except learning_service.NotFoundError:
        return jsonify(error="Not found."), 404
    except learning_service.ValidationError:
        return jsonify(error="Send after=<sequence>."), 400
    except SQLAlchemyError as exc:
        db.session.rollback()
        current_app.logger.warning("Practice reply status unavailable: %s", practice.describe_failure(exc))
        return jsonify(error="Unavailable."), 503
    reply = updates["reply"]
    return jsonify(
        reply={"status": reply["status"], "live": reply["status"] in LIVE},
        # Only a page waiting for a reply polls, so an answered turn means the reply has arrived.
        status_html=render_template("learning/_practice_reply_status.html", reply=reply, polled=True),
        revealed_html=render_template("learning/_practice_revealed.html", revealed=updates["revealed_requirements"]),
        turns=[{"sequence": turn["sequence"],
                "html": render_template("learning/_practice_turn.html", message=turn, titles=titles,
                                        session_id=session_id, is_new=True)}
               for turn in updates["turns"]],
        latest_sequence=updates["latest_sequence"])


def _delete_page(session_id, *, status=200, alert=None):
    try:
        counts = practice.session_counts(current_user.id, session_id)
    except learning_service.NotFoundError:
        abort(404)
    return render_template("learning/practice_delete.html", counts=counts, form=DeletePracticeForm(formdata=None),
                           alert=alert), status


@learning_blueprint.route("/practice/<session_id>/delete", methods=["GET", "POST"])
@login_required
def practice_delete(session_id):
    if request.method == "GET":
        return _delete_page(session_id)
    if not DeletePracticeForm().validate_on_submit():
        return _delete_page(session_id, status=400, alert="This page was open too long. Nothing was deleted: confirm again.")
    try:
        result = practice.delete_session(current_user, session_id)
    except learning_service.NotFoundError:
        # Also what a repeated confirmation sees after the first one deleted the session.
        flash("That practice session doesn't exist or was already deleted.", "practice")
        return redirect(url_for("learning.index"), code=303)
    except SQLAlchemyError as exc:
        db.session.rollback()
        current_app.logger.error("Practice session could not be deleted: %s", practice.describe_failure(exc))
        abort(503)
    flash("Practice session deleted.", "practice")
    return redirect(url_for("learning.concept", concept_id=result["concept_id"]), code=303)


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


@learning_blueprint.get("/practice/<session_id>/submissions/<int:sequence>")
@login_required
def practice_submission(session_id, sequence):
    try:
        detail = practice.submission_detail(current_user.id, session_id, sequence)
    except learning_service.NotFoundError:
        abort(404)
    return render_template("learning/practice_submission.html", detail=detail,
                           artifacts={a["artifact_id"]: a for a in detail["artifacts"]},
                           language_labels=LANGUAGE_LABELS, type_labels=BRIEF_TYPE_LABELS)
