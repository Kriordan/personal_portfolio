"""Private Jobwizard JSON endpoints. Public errors never contain exceptions."""
from flask import Blueprint, jsonify, request
from flask_jwt_extended import get_jwt_identity, jwt_required
from werkzeug.exceptions import Unauthorized

from project.database import db
from project.models import User
from project.services import jobwizard_capture, jobwizard_service as service

jobwizard_api_blueprint = Blueprint("api_jobwizard", __name__, url_prefix="/jobwizard")


@jobwizard_api_blueprint.after_request
def private_response(response):
    response.headers["Cache-Control"] = "private, no-store"
    response.headers["Pragma"] = "no-cache"
    return response


def _user():
    try:
        user = db.session.get(User, int(get_jwt_identity()))
    except (TypeError, ValueError):
        user = None
    if user is None:
        raise Unauthorized()
    return user


def _payload():
    value = request.get_json(silent=True) if request.is_json else request.form.to_dict(flat=True)
    if not isinstance(value, dict):
        raise service.ValidationError()
    return value


@jobwizard_api_blueprint.errorhandler(Unauthorized)
def unauthorized(_error):
    return jsonify(error="Sign in to continue.", code="unauthorized"), 401


@jobwizard_api_blueprint.errorhandler(service.ValidationError)
def invalid(error):
    # Only enum codes, never exception text, are returned as field metadata.
    fields = {key: value for key, value in error.fields.items()
              if key in {"title", "company_name", "listing_url"} and value in {"required", "too_long", "invalid_url"}}
    return jsonify(error="title, company_name, and listing_url are required", code="invalid_job", fields=fields), 400


@jobwizard_api_blueprint.errorhandler(service.NotFoundError)
def missing(_error):
    return jsonify(error="Job not found.", code="not_found"), 404


@jobwizard_api_blueprint.errorhandler(service.ConflictError)
def conflict(_error):
    return jsonify(error="This job or request changed. Load the latest job before saving again.", code="job_conflict"), 409


@jobwizard_api_blueprint.get("/jobs")
@jwt_required()
def api_get_jobs():
    return jsonify(jobs=[service.serialize_job(job) for job in service.list_jobs_for_user(_user().id)])


@jobwizard_api_blueprint.post("/jobs")
@jwt_required()
def api_create_job():
    user, payload = _user(), _payload()
    if "request_id" in payload:
        return jsonify(service.mutate_job(user_id=user.id, payload=payload)), 201
    # Preserve the legacy service entry point, without the old capture side effect.
    if set(payload) - {"title", "company_name", "listing_url"}:
        raise service.ValidationError()
    job = service.create_job_for_user(user_id=user.id, title=payload.get("title"),
        company_name=payload.get("company_name"), listing_url=payload.get("listing_url"))
    return jsonify(job=service.serialize_job(job)), 201


@jobwizard_api_blueprint.get("/jobs/<int:job_id>")
@jwt_required()
def api_get_job(job_id):
    user = _user()
    job = service.get_job_for_user(user_id=user.id, job_id=job_id)
    return jsonify(job=service.serialize_job(job))


@jobwizard_api_blueprint.patch("/jobs/<int:job_id>")
@jwt_required()
def api_update_job(job_id):
    return jsonify(service.mutate_job(user_id=_user().id, job_id=job_id, payload=_payload()))


@jobwizard_api_blueprint.get("/receipts/<request_id>")
@jwt_required()
def api_receipt(request_id):
    return jsonify(receipt=service.mutation_receipt(_user().id, request_id))


@jobwizard_api_blueprint.get("/jobs/<int:job_id>/capture")
@jwt_required()
def api_capture_status(job_id):
    return jsonify(capture=jobwizard_capture.capture_status(user_id=_user().id, job_id=job_id, request_id=request.args.get("request_id")))


@jobwizard_api_blueprint.post("/jobs/<int:job_id>/capture")
@jwt_required()
def api_capture(job_id):
    return jsonify(capture=jobwizard_capture.capture_job(user_id=_user().id, job_id=job_id, payload=_payload()))
