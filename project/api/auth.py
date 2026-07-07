"""JSON auth endpoints for API clients."""

from __future__ import annotations

import sqlalchemy as sa
from flask import Blueprint, current_app, jsonify, request, url_for
from flask_jwt_extended import (
    create_access_token,
    create_refresh_token,
    get_jwt_identity,
    jwt_required,
)
from mailersend import EmailBuilder, MailerSendClient

from project.account.tokens import generate_reset_token, verify_reset_token
from project.database import db
from project.foyer.email_templates import (
    get_email_verification_email_content,
    get_password_reset_email_content,
)
from project.models import User
from project.services import auth_service

auth_api_blueprint = Blueprint("api_auth", __name__, url_prefix="/auth")


def _serialize_user(user: User) -> dict[str, object]:
    return {
        "id": user.id,
        "email": user.email,
        "username": user.username,
        "email_verified": user.email_verified,
        "is_admin": user.is_admin,
    }


def _current_user_from_jwt() -> User | None:
    identity = get_jwt_identity()
    if identity is None:
        return None
    try:
        return db.session.get(User, int(identity))
    except (TypeError, ValueError):
        return None


def _send_verification_email(user: User) -> None:
    verify_url = url_for("account.verify_email", token=user.email_verification_token, _external=True)
    html_content = get_email_verification_email_content(verify_url)
    ms = MailerSendClient(api_key=current_app.config["MAILERSEND_API_KEY"])
    email_message = (
        EmailBuilder()
        .from_email("noreply@keithriordan.com", "Keith Riordan Portfolio")
        .to_many([{"email": user.email, "name": user.username}])
        .subject("Verify your email")
        .html(html_content)
        .build()
    )
    ms.emails.send(email_message)


def _send_password_reset_email(email: str, token: str) -> None:
    reset_url = url_for("account.reset_password", token=token, _external=True)
    html_content = get_password_reset_email_content(reset_url)
    ms = MailerSendClient(api_key=current_app.config["MAILERSEND_API_KEY"])
    email_message = (
        EmailBuilder()
        .from_email("noreply@keithriordan.com", "Keith Riordan Portfolio")
        .to_many([{"email": email, "name": "User"}])
        .subject("Password Reset Request")
        .html(html_content)
        .build()
    )
    ms.emails.send(email_message)


@auth_api_blueprint.post("/login")
def api_login():
    payload = request.get_json(silent=True) or {}
    email = (payload.get("email") or "").strip().lower()
    password = payload.get("password") or ""
    if not email or not password:
        return jsonify({"error": "Email and password are required."}), 400

    user = auth_service.authenticate_user(email=email, password=password)
    if user is None:
        return jsonify({"error": "Invalid credentials."}), 401
    if not user.email_verified:
        return jsonify({"error": "Email verification required."}), 403

    return (
        jsonify(
            {
                "access_token": create_access_token(identity=str(user.id)),
                "refresh_token": create_refresh_token(identity=str(user.id)),
                "user": _serialize_user(user),
            }
        ),
        200,
    )


@auth_api_blueprint.get("/me")
@jwt_required()
def api_me():
    user = _current_user_from_jwt()
    if user is None:
        return jsonify({"error": "User not found."}), 404
    return jsonify({"user": _serialize_user(user)}), 200


@auth_api_blueprint.post("/refresh")
@jwt_required(refresh=True)
def api_refresh():
    identity = get_jwt_identity()
    return jsonify({"access_token": create_access_token(identity=identity)}), 200


@auth_api_blueprint.post("/logout")
@jwt_required()
def api_logout():
    # Stateless JWT logout requires token blocklisting, not yet implemented.
    return jsonify({"message": "Logged out."}), 200


@auth_api_blueprint.post("/signup/<string:token>")
def api_signup(token: str):
    invite = auth_service.get_signup_invitation(token)
    if invite is None:
        return jsonify({"error": "Invalid invite link."}), 404
    if invite.is_expired:
        return jsonify({"error": "Invite link has expired."}), 410
    if invite.is_accepted:
        return jsonify({"error": "Invite link has already been used."}), 409

    payload = request.get_json(silent=True) or {}
    username = (payload.get("username") or "").strip()
    password = payload.get("password") or ""
    email = (payload.get("email") or "").strip().lower()
    if not username or not password:
        return jsonify({"error": "Username and password are required."}), 400
    if email and email != invite.email.lower():
        return jsonify({"error": "Email does not match invitation."}), 400
    if auth_service.email_exists(invite.email):
        return jsonify({"error": "Account already exists for this email."}), 409
    if auth_service.username_exists(username):
        return jsonify({"error": "Username already taken."}), 409

    user = auth_service.create_user_from_invitation(
        invite=invite,
        username=username,
        password=password,
    )

    try:
        _send_verification_email(user)
    except Exception:
        current_app.logger.exception("Failed to send verification email to %s", user.email)
        return (
            jsonify(
                {
                    "message": "Account created, but failed to send verification email.",
                    "user": _serialize_user(user),
                }
            ),
            201,
        )

    return jsonify({"message": "Account created.", "user": _serialize_user(user)}), 201


@auth_api_blueprint.post("/forgot-password")
def api_forgot_password():
    payload = request.get_json(silent=True) or {}
    email = (payload.get("email") or "").strip().lower()
    if not email:
        return jsonify({"error": "Email is required."}), 400
    if auth_service.is_password_reset_rate_limited(email):
        return jsonify({"error": "Too many reset attempts. Please try again later."}), 429

    auth_service.log_password_reset_attempt(email)
    user = db.session.scalar(sa.select(User).where(User.email == email))
    if user:
        token = generate_reset_token(email)
        try:
            _send_password_reset_email(email, token)
        except Exception:
            current_app.logger.exception("Failed to send reset email to %s", email)

    # Prevent email enumeration regardless of account existence.
    return jsonify({"message": "If the account exists, a reset email has been sent."}), 200


@auth_api_blueprint.post("/reset-password/<string:token>")
def api_reset_password(token: str):
    email = verify_reset_token(token)
    if not email:
        return jsonify({"error": "Invalid or expired reset token."}), 400

    user = db.session.scalar(sa.select(User).where(User.email == email))
    if user is None:
        return jsonify({"error": "Invalid or expired reset token."}), 400

    payload = request.get_json(silent=True) or {}
    password = payload.get("password") or ""
    if not password:
        return jsonify({"error": "Password is required."}), 400

    user.set_password(password)
    db.session.commit()
    return jsonify({"message": "Password has been reset."}), 200

