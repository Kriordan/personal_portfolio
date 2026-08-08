from flask import Blueprint, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from project.services import jobwizard_service

from .forms import AddJobForm

jobwizard_blueprint = Blueprint("jobwizard", __name__, template_folder="templates")


@jobwizard_blueprint.route("/jobwizard")
@login_required
def home():
    jobs = jobwizard_service.list_jobs_for_user(current_user.id)
    return render_template("job_list.html", form=AddJobForm(request.form), jobs=jobs)


@jobwizard_blueprint.route("/jobwizard/add/", methods=["GET", "POST"])
@login_required
def create_job():
    error = None
    form = AddJobForm(request.form)
    if form.validate_on_submit():
        jobwizard_service.create_job_for_user(
            user_id=current_user.id,
            title=form.title.data,
            company_name=form.company_name.data,
            listing_url=form.listing_url.data,
        )
        return redirect(url_for(".home"))
    return render_template("jobwizard.html", form=form, error=error)


@jobwizard_blueprint.route("/jobwizard/<int:job_id>", methods=["GET"])
@login_required
def get_job(job_id):
    try:
        job = jobwizard_service.get_job_for_user(
            user_id=current_user.id, job_id=job_id
        )
    except jobwizard_service.NotFoundError:
        return render_template("404.html"), 404
    return render_template("job.html", job=job)
