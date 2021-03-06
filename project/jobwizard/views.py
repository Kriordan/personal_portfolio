from flask import Blueprint, render_template, redirect, request, url_for
import datetime

from .forms import AddJobForm
from project import db
from project.models import Job

jobwizard_blueprint = Blueprint('jobwizard', __name__,
                                template_folder='templates')


@jobwizard_blueprint.route('/jobwizard')
def home():
    jobs = db.session.query(Job)
    return render_template(
        'jobwizard.html',
        form=AddJobForm(request.form),
        jobs=jobs
    )

@jobwizard_blueprint.route('/jobwizard/add/', methods=['GET', 'POST'])
def add_job():
    error = None
    form = AddJobForm(request.form)
    if form.validate_on_submit():
        new_job = Job(
            title = form.title.data,
            company_name = form.company_name.data,
            listing_url = form.listing_url.data,
            posted_date = datetime.datetime.utcnow()
        )
        new_job.render_screenshot()
        db.session.add(new_job)
        db.session.commit()
        return redirect(url_for('.home'))
    return render_template(
        'jobwizard.html',
        form=form,
        error=error
    )

@jobwizard_blueprint.route('/jobwizard/<job_id>', methods=['GET'])
def get_single_job(job_id):
    job = Job.query.filter_by(id=int(job_id)).first()
    return render_template(
        'job.html',
        job=job
    )

