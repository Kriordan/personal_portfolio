"""This file defines the routes for the account blueprint."""

from urllib.parse import urlsplit

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
from project.account.tokens import generate_reset_token
from project.foyer.email_templates import (
    get_email_verification_email_content,
    get_password_reset_email_content,
    get_signup_invitation_email_content,
)
from project.models import (
    User,
)
from project.services import auth_service

account_blueprint = Blueprint("account", __name__, template_folder="templates")

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
        user = auth_service.authenticate_user(
            email=form.email.data,
            password=form.password.data,
        )
        if user is None:
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
    auth_service.generate_email_verification(user)


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

    invite = auth_service.get_signup_invitation(token)
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

        if auth_service.email_exists(invite.email):
            flash("An account with that email already exists. Please log in.", "info")
            return redirect(url_for("account.login"))

        if auth_service.username_exists(form.username.data):
            flash("That username is already taken.", "danger")
            form.email.data = invite.email
            return render_template("signup.html", form=form)

        user = auth_service.create_user_from_invitation(
            invite=invite,
            username=form.username.data,
            password=form.password.data,
        )

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
    user = auth_service.get_user_by_verification_token(token)
    status = auth_service.get_verification_status(user)
    if status == "invalid":
        flash("Invalid verification link.", "danger")
        return redirect(url_for("account.login"))

    if status == "expired":
        flash("The verification link has expired. Please request a new one.", "danger")
        return redirect(url_for("account.login"))

    if status == "verified":
        flash("Email already verified. Please log in.", "info")
        return redirect(url_for("account.login"))

    auth_service.verify_email_token(token)
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

    user, status = auth_service.prepare_verification_resend(email)
    if status == "user_not_found":
        flash("No account found for that email.", "danger")
        return redirect(url_for("account.login"))

    if status == "already_verified":
        flash("Your email is already verified. Please log in.", "info")
        return redirect(url_for("account.login"))

    if status == "rate_limited":
        flash("Too many verification requests. Please try again later.", "warning")
        return redirect(url_for("account.login"))

    try:
        if user is None:
            raise ValueError("Verification resend user context missing.")
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

        invite, status = auth_service.create_site_invitation(
            email=email,
            invited_by=current_user,
        )
        if status == "user_exists":
            flash("An account with that email already exists.", "info")
            return redirect(url_for("account.admin_invites"))

        if status == "invite_exists":
            flash("An active invite already exists for that email.", "info")
            return redirect(url_for("account.admin_invites"))

        try:
            if invite is None:
                raise ValueError("Invitation context missing after creation.")
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

    site_invites, list_invites = auth_service.get_admin_invites()

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
    return auth_service.is_password_reset_rate_limited(email)


def log_reset_attempt(email: str) -> None:
    """Log a password reset attempt for rate limiting."""
    auth_service.log_password_reset_attempt(email)


def is_verification_rate_limited(email: str) -> bool:
    """Check if the email has exceeded the rate limit for verification resends."""
    return auth_service.is_verification_rate_limited(email)


def log_verification_attempt(email: str) -> None:
    """Log a verification resend attempt for rate limiting."""
    auth_service.log_verification_attempt(email)


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

        user, status = auth_service.prepare_password_reset(email)
        if status == "rate_limited":
            flash("Too many reset attempts. Please try again later.")
            return render_template("forgot_password.html", form=form)

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

    user = auth_service.get_user_from_reset_token(token)
    if not user:
        flash("The password reset link is invalid or has expired.", "error")
        return redirect(url_for("account.forgot_password"))

    form = ResetPasswordForm()

    if form.validate_on_submit():
        auth_service.reset_user_password(user=user, password=form.password.data)
        flash("Your password has been reset. Please log in with your new password.")
        return redirect(url_for("account.login"))

    return render_template("reset_password.html", form=form)
