"""Native feedback responses and explicitly rated follow-up practice."""
from uuid import uuid4

from flask import abort, current_app, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy.exc import SQLAlchemyError

from project.database import db
from project.services import feedback_review_service as review, learning_service, practice_service as practice

from . import learning_blueprint
from .forms import ConceptRatingForm, FeedbackAnnotationForm
from .navigation import workspace_navigation


def _snapshot_url(session_id, sequence, finding_id):
    return url_for("learning.practice_submission", session_id=session_id, sequence=sequence, _anchor="finding-" + finding_id)


def _rescue(form, session_id, sequence, finding_id, *, kind, heading, message, status, latest=None):
    return render_template("learning/feedback_response_rescue.html", form=form, kind=kind,
        heading=heading, message=message, latest=latest,
        action_url=request.full_path.rstrip("?") if kind == "read" else request.path,
        snapshot_url=_snapshot_url(session_id, sequence, finding_id)), status


@learning_blueprint.post("/practice/<session_id>/submissions/<int:sequence>/feedback/<finding_id>/response")
@login_required
def practice_feedback_annotation(session_id, sequence, finding_id):
    form = FeedbackAnnotationForm(prefix=f"annotation-{finding_id}-")
    if not form.validate_on_submit():
        return _rescue(form, session_id, sequence, finding_id, kind="annotation", status=400,
            heading="Your response is still here", message="Nothing was saved. Check your response and try again.")
    try:
        review.annotate(current_user, session_id, sequence, finding_id, decision=form.decision.data,
            note=form.note.data, expected_revision=form.expected_revision.data, request_id=form.request_id.data)
    except learning_service.NotFoundError:
        abort(404)
    except review.AnnotationConflict as exc:
        # IntegerField renders submitted raw_data ahead of .data; rebuild the form
        # so the explicit replacement targets the revision the learner just saw.
        form = FeedbackAnnotationForm(prefix=f"annotation-{finding_id}-", formdata=None, data={
            "decision": form.decision.data, "note": form.note.data,
            "expected_revision": exc.current["revision"], "request_id": str(uuid4())})
        return _rescue(form, session_id, sequence, finding_id, kind="annotation", status=409,
            heading="Your response changed elsewhere", message="Your draft is below. Compare both versions before saving.", latest=exc.current)
    except practice.RequestConflictError:
        form.request_id.data = str(uuid4())
        return _rescue(form, session_id, sequence, finding_id, kind="annotation", status=409,
            heading="Check your response", message="This request was used for another change. Your draft is below; review it before saving.")
    except learning_service.ValidationError as exc:
        return _rescue(form, session_id, sequence, finding_id, kind="annotation", status=400,
            heading="Your response is still here", message=str(exc))
    except SQLAlchemyError as exc:
        db.session.rollback()
        current_app.logger.warning("Feedback response unconfirmed: %s", practice.describe_failure(exc))
        return _rescue(form, session_id, sequence, finding_id, kind="annotation", status=503,
            heading="Response not confirmed", message="Your choice and note are below. Retry safely with this form; a saved response will not be duplicated.")
    flash("Your response was saved.", "practice")
    return redirect(_snapshot_url(session_id, sequence, finding_id), code=303)


def _attempt():
    values = {key: request.args.get(key) for key in ("card_id", "content_version", "expected_revision", "request_id")}
    for key in ("content_version", "expected_revision"):
        raw = values[key] or ""
        if not raw.isascii() or not raw.isdecimal() or len(raw) > 10:
            abort(400)
        values[key] = int(raw)
    return values


@learning_blueprint.route("/practice/<session_id>/submissions/<int:sequence>/feedback/<finding_id>/review", methods=["GET", "POST"])
@login_required
def practice_feedback_review(session_id, sequence, finding_id):
    form = ConceptRatingForm()
    error, status, card, revealed = None, 200, None, False
    if request.method == "POST":
        if not form.validate_on_submit():
            return _rescue(form, session_id, sequence, finding_id, kind="rating", status=400,
                heading="Rating not saved", message="Check this form and retry the same rating.")
        try:
            result = review.rate_review(current_user, session_id, sequence, finding_id,
                **{key: getattr(form, key).data for key in ("card_id", "content_version", "expected_revision", "request_id", "rating")})
        except learning_service.NotFoundError:
            abort(404)
        except learning_service.ValidationError:
            abort(400)
        except review.DecisionRequired:
            error, status = "Your response no longer agrees with this finding. No new rating was saved.", 409
        except learning_service.ConflictError:
            error, status = "This question changed or was already rated. Load the remaining practice before rating again.", 409
        except SQLAlchemyError as exc:
            db.session.rollback()
            current_app.logger.warning("Feedback practice rating unconfirmed: %s", practice.describe_failure(exc))
            return _rescue(form, session_id, sequence, finding_id, kind="rating", status=503,
                heading="Rating not confirmed", message="Retry the same rating safely. If it was saved, this request will recover that result.")
        else:
            flash("Review saved. " + result["next_review_display"], "concept-review")
            return redirect(request.path, code=303)
    try:
        detail = review.review_detail(current_user.id, session_id, sequence, finding_id)
        if request.method == "GET" and request.args:
            card = review.review_card(current_user.id, session_id, sequence, finding_id, **_attempt())
            form = ConceptRatingForm(formdata=None, data=_attempt())
            revealed = True
        elif status == 200 and detail["questions"]:
            card = detail["questions"][0]
            form = ConceptRatingForm(formdata=None, card_id=card["card_id"], content_version=card["content_version"],
                                     expected_revision=card["progress_revision"], request_id=str(uuid4()))
    except learning_service.NotFoundError:
        abort(404)
    except learning_service.ValidationError:
        abort(400)
    except review.DecisionRequired:
        error, status = "Your response no longer agrees with this finding. Return to feedback to review your choice.", 409
    except learning_service.ConflictError:
        error, status = "This question changed or was already rated. Load the remaining practice before rating again.", 409
    except SQLAlchemyError as exc:
        db.session.rollback()
        current_app.logger.warning("Feedback practice read unavailable: %s", practice.describe_failure(exc))
        return _rescue(form, session_id, sequence, finding_id, kind="read", status=503,
            heading="Practice is temporarily unavailable", message="Your saved responses and ratings have not been changed. Reload to continue.")
    workspace = workspace_navigation(detail["session"]["concept_id"], mode="review", session=detail["session"])
    workspace["review_url"] = request.path
    remediation_url = url_for("learning.concept", concept_id=card["note_id"],
        practice_session=session_id if card["note_id"] == detail["session"]["concept_id"] else None,
        _anchor=card["remediation_section_id"]) if card else None
    return render_template("learning/feedback_review.html", detail=detail, workspace=workspace,
        snapshot_url=_snapshot_url(session_id, sequence, finding_id), card=card, form=form,
        revealed=revealed, error=error, stale=status == 409, retry_same=False, remediation_url=remediation_url), status
