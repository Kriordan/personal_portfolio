"""JSON jobwizard endpoints for API clients."""

from __future__ import annotations

from typing import Any

from flask import Blueprint, jsonify, request
from flask_jwt_extended import get_jwt_identity, jwt_required

from project.database import db
from project.models import User
from project.services import jobwizard_service

jobwizard_api_blueprint = Blueprint("api_jobwizard", __name__, url_prefix="/jobwizard")


def _current_user_from_jwt() -> User | None:
    identity = get_jwt_identity()
    if identity is None:
        return None
    try:
        return db.session.get(User, int(identity))
    except (TypeError, ValueError):
        return None


def _request_payload() -> dict[str, Any]:
    if request.is_json:
        return request.get_json(silent=True) or {}
    return request.form.to_dict(flat=True)


@jobwizard_api_blueprint.get("/jobs")
@jwt_required()
def api_get_jobs():
    user = _current_user_from_jwt()
    if user is None:
        return jsonify({"error": "Unauthorized."}), 401

    jobs = jobwizard_service.list_jobs_for_user(user.id)
    return jsonify({"jobs": [jobwizard_service.serialize_job(job) for job in jobs]}), 200


@jobwizard_api_blueprint.post("/jobs")
@jwt_required()
def api_create_job():
    user = _current_user_from_jwt()
    if user is None:
        return jsonify({"error": "Unauthorized."}), 401

    payload = _request_payload()
    try:
        job = jobwizard_service.create_job_for_user(
            user_id=user.id,
            title=payload.get("title", ""),
            company_name=payload.get("company_name", ""),
            listing_url=payload.get("listing_url", ""),
        )
    except jobwizard_service.ValidationError:
        return jsonify(
            {"error": "title, company_name, and listing_url are required"}
        ), 400

    return jsonify({"job": jobwizard_service.serialize_job(job)}), 201


@jobwizard_api_blueprint.get("/jobs/<int:job_id>")
@jwt_required()
def api_get_job(job_id: int):
    user = _current_user_from_jwt()
    if user is None:
        return jsonify({"error": "Unauthorized."}), 401

    try:
        job = jobwizard_service.get_job_for_user(user_id=user.id, job_id=job_id)
    except jobwizard_service.NotFoundError:
        return jsonify({"error": "Job not found."}), 404
    return jsonify({"job": jobwizard_service.serialize_job(job)}), 200
