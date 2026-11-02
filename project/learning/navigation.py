"""Read-only navigation between a concept and one explicitly selected session."""
from flask import abort, request, url_for
from flask_login import current_user

from project.services import learning_service, practice_service


def selected_session(concept):
    if not practice_service.enabled():
        return None
    session_id = request.args.get("practice_session")
    if request.method == "POST":
        session_id = request.form.get("practice_session", session_id)
    if session_id is not None:
        try:
            session = practice_service.session_summary(current_user.id, session_id)
        except learning_service.NotFoundError:
            abort(404)
        if session["concept_id"] != concept["id"]:
            abort(404)
        return session
    sessions = practice_service.list_sessions(current_user.id,
        exercise_ids=concept["content"]["exercise_ids"], limit=1)
    return next((session for session in sessions if session["concept_id"] == concept["id"]), None)


def workspace_navigation(concept_id, *, mode, session=None, practice_enabled=None):
    """Build URLs from already-authorized data; no DB reads during practice rescue."""
    if practice_enabled is None:
        practice_enabled = practice_service.enabled()
    selected = {"practice_session": session["id"]} if session else {}
    return dict(concept_id=concept_id, title=concept_id.replace("-", " ").capitalize(), mode=mode,
        session=session, practice_enabled=practice_enabled,
        learn_url=url_for("learning.concept", concept_id=concept_id, **selected),
        review_url=url_for("learning.concept_review", concept_id=concept_id, **selected),
        **{f"{view}_url": url_for("learning.practice_workspace", session_id=session["id"], view=view)
           if session else url_for("learning.concept_practice", concept_id=concept_id, view=view)
           for view in ("discuss", "build")})
