"""This file defines the routes for the account blueprint."""

from datetime import datetime, timedelta, timezone
from urllib.parse import urlsplit

import sqlalchemy as sa
from flask import (
    Blueprint,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    url_for,
)
from flask_login import current_user, login_user, logout_user
from mailersend import EmailBuilder, MailerSendClient

from project.account.forms import ForgotPasswordForm, LoginForm, ResetPasswordForm
from project.account.tokens import generate_reset_token, verify_reset_token
from project.database import db
from project.foyer.email_templates import get_password_reset_email_content
from project.models import PasswordResetAttempt, User

account_blueprint = Blueprint("account", __name__, template_folder="templates")

MAX_RESET_ATTEMPTS_PER_HOUR = 3


@account_blueprint.route("/login", methods=["GET", "POST"])
def login():
    """
    The login route.
    """
    if current_user.is_authenticated:
        return redirect(url_for("foyer.home"))
    form = LoginForm()
    if form.validate_on_submit():
        user = db.session.scalar(sa.select(User).where(User.email == form.email.data))
        if (
            user is None
            or not user.check_password(form.password.data)
            or not user.is_active
        ):
            flash("Invalid username or password", "error")
            return redirect(url_for("account.login"))
        login_user(user, remember=form.remember_me.data)
        next_page = request.args.get("next")
        if not next_page or urlsplit(next_page).netloc != "":
            next_page = url_for("foyer.home")
        return redirect(next_page)
    return render_template("login.html", title="Sign In", form=form)


@account_blueprint.route("/logout")
def logout():
    """
    The logout route.
    """
    logout_user()
    return redirect(url_for("foyer.home"))


def is_rate_limited(email: str) -> bool:
    """Check if the email has exceeded the rate limit for password reset attempts."""
    one_hour_ago = datetime.now(timezone.utc) - timedelta(hours=1)
    recent_attempts = db.session.scalar(
        sa.select(sa.func.count(PasswordResetAttempt.id)).where(
            PasswordResetAttempt.email == email,
            PasswordResetAttempt.attempted_at >= one_hour_ago,
        )
    )
    return recent_attempts >= MAX_RESET_ATTEMPTS_PER_HOUR


def log_reset_attempt(email: str) -> None:
    """Log a password reset attempt for rate limiting."""
    attempt = PasswordResetAttempt(email=email)
    db.session.add(attempt)
    db.session.commit()


@account_blueprint.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    """
    Handle forgot password requests.
    """
    if current_user.is_authenticated:
        return redirect(url_for("foyer.home"))

    form = ForgotPasswordForm()

    if form.validate_on_submit():
        email = form.email.data.lower()

        if is_rate_limited(email):
            flash("Too many reset attempts. Please try again later.")
            return render_template("forgot_password.html", form=form)

        log_reset_attempt(email)

        user = db.session.scalar(sa.select(User).where(User.email == email))

        if user:
            token = generate_reset_token(email)
            reset_url = url_for("account.reset_password", token=token, _external=True)
            html_content = get_password_reset_email_content(reset_url)

            try:
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
            except Exception as err:
                print(f"Error sending password reset email: {err}")

        # Always show success message to prevent email enumeration
        flash(
            "If an account exists with that email, you will receive a password reset link."
        )
        return redirect(url_for("account.login"))

    return render_template("forgot_password.html", form=form)


@account_blueprint.route("/reset-password/<token>", methods=["GET", "POST"])
def reset_password(token):
    """
    Handle password reset with a valid token.
    """
    if current_user.is_authenticated:
        return redirect(url_for("foyer.home"))

    email = verify_reset_token(token)
    if not email:
        flash("The password reset link is invalid or has expired.", "error")
        return redirect(url_for("account.forgot_password"))

    user = db.session.scalar(sa.select(User).where(User.email == email))
    if not user:
        flash("The password reset link is invalid or has expired.", "error")
        return redirect(url_for("account.forgot_password"))

    form = ResetPasswordForm()

    if form.validate_on_submit():
        user.set_password(form.password.data)
        db.session.commit()
        flash("Your password has been reset. Please log in with your new password.")
        return redirect(url_for("account.login"))

    return render_template("reset_password.html", form=form)
