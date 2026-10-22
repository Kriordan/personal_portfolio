from uuid import uuid4

from flask import Blueprint, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from project.services import jobwizard_capture, jobwizard_service as service
from .forms import AddJobForm, JobActionForm

jobwizard_blueprint = Blueprint("jobwizard", __name__, template_folder="templates")


@jobwizard_blueprint.after_request
def private_response(response):
    response.headers["Cache-Control"] = "private, no-store"
    return response


@jobwizard_blueprint.errorhandler(service.NotFoundError)
def missing(_error):
    return render_template("404.html"), 404


def _form(job=None):
    form = AddJobForm(request.form if request.method == "POST" else None, obj=job)
    if request.method != "POST":
        form.request_id.data = str(uuid4())
        form.expected_revision.data = str(job.revision) if job else ""
    return form


@jobwizard_blueprint.route("/jobwizard")
@login_required
def home():
    view = request.args.get("view", "active")
    if view not in {"active", "archived", "all"}:
        view = "active"
    jobs = [service.serialize_job(job) for job in service.list_jobs_for_user(current_user.id)]
    jobs = [job for job in jobs if view == "all" or bool(job["archived_at"]) == (view == "archived")]
    return render_template("job_list.html", form=_form(), jobs=jobs, view=view)


@jobwizard_blueprint.route("/jobwizard/add/", methods=["GET", "POST"])
@login_required
def create_job():
    return _save()


@jobwizard_blueprint.route("/jobwizard/<int:job_id>/edit", methods=["GET", "POST"])
@login_required
def edit_job(job_id):
    return _save(service.get_job_for_user(user_id=current_user.id, job_id=job_id))


def _save(job=None):
    form, error, status = _form(job), None, 200
    if form.validate_on_submit():
        payload = {key: getattr(form, key).data for key in ("title", "company_name", "listing_url")}
        if form.request_id.data:
            payload["request_id"] = form.request_id.data
        try:
            if job:
                payload["expected_revision"] = int(form.expected_revision.data)
            result = service.mutate_job(user_id=current_user.id, job_id=job.id if job else None, payload=payload)
            return redirect(url_for(".get_job", job_id=result["job"]["id"]))
        except (service.ValidationError, ValueError):
            error, status = "Check the required fields, lengths and HTTP(S) listing URL.", 400
        except service.ConflictError:
            error, status = "The job changed elsewhere. Your draft is below; open the current job before retrying.", 409
    elif request.method == "POST":
        status = 400
    return render_template("job_form.html", form=form, error=error, job=job), status


@jobwizard_blueprint.route("/jobwizard/<int:job_id>", methods=["GET"])
@login_required
def get_job(job_id):
    job = service.get_job_for_user(user_id=current_user.id, job_id=job_id)
    capture = jobwizard_capture.capture_status(user_id=current_user.id, job_id=job_id)
    form = JobActionForm(request_id=str(uuid4()), expected_revision=str(job.revision))
    return render_template("job.html", job=service.serialize_job(job), capture=capture, form=form)


@jobwizard_blueprint.post("/jobwizard/<int:job_id>/action")
@login_required
def job_action(job_id):
    service.get_job_for_user(user_id=current_user.id, job_id=job_id)
    form = JobActionForm(request.form)
    if not form.validate_on_submit():
        return render_template("job_action_error.html", job_id=job_id, message="Invalid form. Return to the job and try again."), 400
    try:
        payload = dict(request_id=form.request_id.data, expected_revision=int(form.expected_revision.data))
        if form.action.data == "capture":
            jobwizard_capture.capture_job(user_id=current_user.id, job_id=job_id, payload=payload)
        elif form.action.data in {"archive", "restore"}:
            service.mutate_job(user_id=current_user.id, job_id=job_id, payload={**payload, "archived": form.action.data == "archive"})
        else:
            raise service.ValidationError()
    except (service.ValidationError, ValueError):
        return render_template("job_action_error.html", job_id=job_id, message="Invalid action. Return to the job and try again."), 400
    except service.ConflictError:
        return render_template("job_action_error.html", job_id=job_id, message="This job changed. Return to the job to see the latest version."), 409
    return redirect(url_for(".get_job", job_id=job_id))
