"""This file defines the routes for the account blueprint."""

import secrets
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
    session,
    url_for,
)
from flask_login import current_user, login_required, login_user, logout_user
from mailersend import EmailBuilder, MailerSendClient

from project.account.forms import (
    AdminInviteForm,
    ForgotPasswordForm,
    LoginForm,
    ResendVerificationForm,
    ResetPasswordForm,
    SignupForm,
)
from project.account.tokens import generate_reset_token, verify_reset_token
from project.database import db
from project.foyer.email_templates import (
    get_email_verification_email_content,
    get_password_reset_email_content,
    get_signup_invitation_email_content,
)
from project.models import (
    EmailVerificationAttempt,
    ListInvitation,
    PasswordResetAttempt,
    SiteInvitation,
    User,
)

account_blueprint = Blueprint("account", __name__, template_folder="templates")

MAX_RESET_ATTEMPTS_PER_HOUR = 3
MAX_VERIFICATION_RESENDS_PER_HOUR = 3


@account_blueprint.route("/login", methods=["GET", "POST"])
def login():
    """
    The login route.
    """
    if current_user.is_authenticated:
        pending_token = session.pop("pending_invitation_token", None)
        if pending_token:
            return redirect(url_for("lists.accept_invitation", token=pending_token))
        return redirect(url_for("foyer.home"))

    form = LoginForm()
    resend_form = ResendVerificationForm()
    if form.validate_on_submit():
        user = db.session.scalar(sa.select(User).where(User.email == form.email.data))
        if (
            user is None
            or not user.check_password(form.password.data)
            or not user.is_active
        ):
            flash("Invalid username or password", "error")
            return redirect(url_for("account.login"))
        if not user.email_verified:
            flash("Please verify your email before logging in.", "warning")
            session["pending_verification_email"] = user.email
            return redirect(url_for("account.login"))
        login_user(user, remember=form.remember_me.data)
        session.pop("pending_verification_email", None)

        pending_token = session.pop("pending_invitation_token", None)
        if pending_token:
            return redirect(url_for("lists.accept_invitation", token=pending_token))

        next_page = request.args.get("next")
        if not next_page or urlsplit(next_page).netloc != "":
            next_page = url_for("foyer.home")
        return redirect(next_page)
    return render_template(
        "login.html", title="Sign In", form=form, resend_form=resend_form
    )


def generate_email_verification(user: User) -> None:
    """Generate and store an email verification token for the user."""
    user.email_verification_token = secrets.token_urlsafe(32)
    user.email_verification_expires_at = datetime.now(timezone.utc) + timedelta(hours=1)


def send_verification_email(user: User) -> None:
    """Send an email verification message."""
    verify_url = url_for(
        "account.verify_email", token=user.email_verification_token, _external=True
    )
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


@account_blueprint.route("/signup/<token>", methods=["GET", "POST"])
def signup(token):
    """
    Invitation-only signup route.
    """
    if current_user.is_authenticated:
        return redirect(url_for("foyer.home"))

    site_invite = db.session.scalar(
        sa.select(SiteInvitation).where(SiteInvitation.token == token)
    )
    list_invite = None
    if not site_invite:
        list_invite = db.session.scalar(
            sa.select(ListInvitation).where(ListInvitation.token == token)
        )

    invite = site_invite or list_invite
    if not invite:
        flash("Invalid invite link.", "danger")
        return redirect(url_for("account.login"))

    if invite.is_expired:
        flash("This invite link has expired. Please request a new one.", "danger")
        return redirect(url_for("account.login"))

    if invite.is_accepted:
        flash("This invite link has already been used. Please log in.", "info")
        return redirect(url_for("account.login"))

    form = SignupForm()

    if form.validate_on_submit():
        if form.email.data and form.email.data.lower() != invite.email.lower():
            flash("Email address does not match the invitation.", "danger")
            form.email.data = invite.email
            return render_template("signup.html", form=form)

        existing_user = db.session.scalar(
            sa.select(User).where(User.email == invite.email)
        )
        if existing_user:
            flash("An account with that email already exists. Please log in.", "info")
            return redirect(url_for("account.login"))

        existing_username = db.session.scalar(
            sa.select(User).where(User.username == form.username.data)
        )
        if existing_username:
            flash("That username is already taken.", "danger")
            form.email.data = invite.email
            return render_template("signup.html", form=form)

        user = User(email=invite.email, username=form.username.data)
        user.set_password(form.password.data)
        generate_email_verification(user)
        db.session.add(user)

        # SiteInvitations are accepted immediately at signup.
        # ListInvitations are intentionally deferred to email verification,
        # where the user is also added to the list's shared_with (see verify_email).
        if isinstance(invite, SiteInvitation):
            invite.accept()

        db.session.commit()

        try:
            send_verification_email(user)
        except Exception:
            current_app.logger.exception(
                "Failed to send verification email to %s", user.email
            )
            flash(
                "Your account was created, but we couldn't send the verification email. "
                "Please request a new one from your account settings.",
                "warning",
            )

        return render_template("verify_email_sent.html", email=user.email)

    # Always display the invite email in the form (GET requests and validation errors)
    form.email.data = invite.email
    return render_template("signup.html", form=form)


@account_blueprint.route("/verify-email/<token>")
def verify_email(token):
    """
    Verify a user's email address.
    """
    user = db.session.scalar(
        sa.select(User).where(User.email_verification_token == token)
    )
    if not user:
        flash("Invalid verification link.", "danger")
        return redirect(url_for("account.login"))

    if (
        user.email_verification_expires_at is None
        or datetime.now(timezone.utc) > user.email_verification_expires_at
    ):
        flash("The verification link has expired. Please request a new one.", "danger")
        return redirect(url_for("account.login"))

    if user.email_verified:
        flash("Email already verified. Please log in.", "info")
        return redirect(url_for("account.login"))

    user.email_verified = True
    user.email_verification_token = None
    user.email_verification_expires_at = None

    pending_list_invites = (
        ListInvitation.query.filter_by(email=user.email)
        .filter(ListInvitation.accepted_at.is_(None))
        .all()
    )
    for invite in pending_list_invites:
        if invite.is_expired:
            continue
        custom_list = invite.custom_list
        if user not in custom_list.shared_with:
            custom_list.shared_with.append(user)
        invite.accept()

    db.session.commit()
    session.pop("pending_verification_email", None)
    flash("Your email has been verified. Please log in.", "success")
    return redirect(url_for("account.login"))


@account_blueprint.route("/resend-verification", methods=["POST"])
def resend_verification():
    """Resend a verification email for users who haven't verified yet."""
    resend_form = ResendVerificationForm()
    if not resend_form.validate_on_submit():
        return redirect(url_for("account.login"))

    email = session.get("pending_verification_email")
    if not email:
        flash("No pending verification request found.", "warning")
        return redirect(url_for("account.login"))

    user = db.session.scalar(sa.select(User).where(User.email == email))
    if not user:
        flash("No account found for that email.", "danger")
        return redirect(url_for("account.login"))

    if user.email_verified:
        flash("Your email is already verified. Please log in.", "info")
        return redirect(url_for("account.login"))

    if is_verification_rate_limited(email):
        flash("Too many verification requests. Please try again later.", "warning")
        return redirect(url_for("account.login"))

    log_verification_attempt(email)
    generate_email_verification(user)
    db.session.commit()

    try:
        send_verification_email(user)
    except Exception:
        current_app.logger.exception(
            "Failed to resend verification email to %s", user.email
        )
        session.pop("pending_verification_email", None)
        flash(
            "We couldn't send the verification email. Please try again later.",
            "warning",
        )
        return redirect(url_for("account.login"))

    session.pop("pending_verification_email", None)
    flash("Verification email resent. Please check your inbox.", "success")
    return redirect(url_for("account.login"))


def require_admin_access():
    if not current_user.is_authenticated or not current_user.is_admin:
        flash("You do not have access to that page.", "danger")
        return False
    return True


@account_blueprint.route("/admin/invites", methods=["GET", "POST"])
@login_required
def admin_invites():
    if not require_admin_access():
        return redirect(url_for("foyer.home"))

    form = AdminInviteForm()
    if form.validate_on_submit():
        email = form.email.data.strip().lower()

        existing_user = db.session.scalar(sa.select(User).where(User.email == email))
        if existing_user:
            flash("An account with that email already exists.", "info")
            return redirect(url_for("account.admin_invites"))

        existing_invite = db.session.scalar(
            sa.select(SiteInvitation)
            .where(SiteInvitation.email == email)
            .where(SiteInvitation.accepted_at.is_(None))
        )
        if existing_invite and not existing_invite.is_expired:
            flash("An active invite already exists for that email.", "info")
            return redirect(url_for("account.admin_invites"))

        invite = SiteInvitation.create_invitation(email=email)
        invite.invited_by = current_user
        db.session.add(invite)
        db.session.commit()

        try:
            invite_url = url_for("account.signup", token=invite.token, _external=True)
            html_content = get_signup_invitation_email_content(invite_url)
            ms = MailerSendClient(api_key=current_app.config["MAILERSEND_API_KEY"])
            email_message = (
                EmailBuilder()
                .from_email("noreply@keithriordan.com", "Keith Riordan Portfolio")
                .to_many([{"email": email, "name": email.split("@")[0]}])
                .subject("You're invited to join")
                .html(html_content)
                .build()
            )
            ms.emails.send(email_message)
            flash("Invitation sent successfully.", "success")
        except Exception:
            current_app.logger.exception("Failed to send invitation email to %s", email)
            flash("Failed to send invitation email. Please try again.", "danger")

        return redirect(url_for("account.admin_invites"))

    site_invites = SiteInvitation.query.order_by(SiteInvitation.created_at.desc()).all()
    list_invites = ListInvitation.query.order_by(ListInvitation.created_at.desc()).all()

    return render_template(
        "admin_invites.html",
        form=form,
        site_invites=site_invites,
        list_invites=list_invites,
    )


@account_blueprint.route("/logout")
def logout():
    """
    The logout route.
    """
    session.pop("pending_verification_email", None)
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


def is_verification_rate_limited(email: str) -> bool:
    """Check if the email has exceeded the rate limit for verification resends."""
    one_hour_ago = datetime.now(timezone.utc) - timedelta(hours=1)
    recent_attempts = db.session.scalar(
        sa.select(sa.func.count(EmailVerificationAttempt.id)).where(
            EmailVerificationAttempt.email == email,
            EmailVerificationAttempt.attempted_at >= one_hour_ago,
        )
    )
    return recent_attempts >= MAX_VERIFICATION_RESENDS_PER_HOUR


def log_verification_attempt(email: str) -> None:
    """Log a verification resend attempt for rate limiting."""
    attempt = EmailVerificationAttempt(email=email)
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
