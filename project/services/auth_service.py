"""Business logic for authentication and account workflows."""

from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone
from typing import Literal

import sqlalchemy as sa

from project.account.tokens import verify_reset_token
from project.database import db
from project.models import (
    EmailVerificationAttempt,
    ListInvitation,
    PasswordResetAttempt,
    SiteInvitation,
    User,
)

MAX_RESET_ATTEMPTS_PER_HOUR = 3
MAX_VERIFICATION_RESENDS_PER_HOUR = 3


def authenticate_user(*, email: str, password: str) -> User | None:
    """Authenticate active user by email/password."""
    user = db.session.scalar(sa.select(User).where(User.email == email))
    if user is None or not user.check_password(password) or not user.is_active:
        return None
    return user


def generate_email_verification(user: User) -> None:
    """Set verification token and expiry on a user."""
    user.email_verification_token = secrets.token_urlsafe(32)
    user.email_verification_expires_at = datetime.now(timezone.utc) + timedelta(hours=1)


def get_signup_invitation(token: str) -> SiteInvitation | ListInvitation | None:
    """Resolve signup token to a site or list invitation."""
    site_invite = db.session.scalar(sa.select(SiteInvitation).where(SiteInvitation.token == token))
    if site_invite:
        return site_invite

    return db.session.scalar(sa.select(ListInvitation).where(ListInvitation.token == token))


def email_exists(email: str) -> bool:
    """Return whether user email already exists."""
    return db.session.scalar(sa.select(User).where(User.email == email)) is not None


def username_exists(username: str) -> bool:
    """Return whether username already exists."""
    return db.session.scalar(sa.select(User).where(User.username == username)) is not None


def create_user_from_invitation(
    *,
    invite: SiteInvitation | ListInvitation,
    username: str,
    password: str,
) -> User:
    """Create user from accepted invitation preconditions."""
    user = User(email=invite.email, username=username)
    user.set_password(password)
    generate_email_verification(user)
    db.session.add(user)

    if isinstance(invite, SiteInvitation):
        invite.accept()

    db.session.commit()
    return user


def verify_email_token(token: str) -> User | None:
    """Verify email token, attach pending list invites, and commit."""
    user = db.session.scalar(sa.select(User).where(User.email_verification_token == token))
    if not user:
        return None

    if user.email_verification_expires_at is None:
        return None

    if datetime.now(timezone.utc) > user.email_verification_expires_at:
        return None

    if user.email_verified:
        return user

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
    return user


def get_user_by_email(email: str) -> User | None:
    """Look up user by normalized email."""
    return db.session.scalar(sa.select(User).where(User.email == email))


def get_user_by_verification_token(token: str) -> User | None:
    """Look up user by email verification token."""
    return db.session.scalar(sa.select(User).where(User.email_verification_token == token))


def get_verification_status(user: User | None) -> Literal["invalid", "expired", "verified", "pending"]:
    """Classify verification state for a token lookup result."""
    if user is None:
        return "invalid"
    if user.email_verified:
        return "verified"
    if (
        user.email_verification_expires_at is None
        or datetime.now(timezone.utc) > user.email_verification_expires_at
    ):
        return "expired"
    return "pending"


def create_site_invitation(*, email: str, invited_by: User) -> tuple[SiteInvitation | None, str]:
    """Create a site invitation, returning status for existing records."""
    existing_user = get_user_by_email(email)
    if existing_user:
        return None, "user_exists"

    existing_invite = db.session.scalar(
        sa.select(SiteInvitation)
        .where(SiteInvitation.email == email)
        .where(SiteInvitation.accepted_at.is_(None))
    )
    if existing_invite and not existing_invite.is_expired:
        return None, "invite_exists"

    invite = SiteInvitation.create_invitation(email=email)
    invite.invited_by = invited_by
    db.session.add(invite)
    db.session.commit()
    return invite, "created"


def get_admin_invites() -> tuple[list[SiteInvitation], list[ListInvitation]]:
    """Return site and list invites for admin views."""
    site_invites = SiteInvitation.query.order_by(SiteInvitation.created_at.desc()).all()
    list_invites = ListInvitation.query.order_by(ListInvitation.created_at.desc()).all()
    return site_invites, list_invites


def prepare_password_reset(email: str) -> tuple[User | None, str]:
    """Rate-limit and log reset attempts; return status and target user."""
    if is_password_reset_rate_limited(email):
        return None, "rate_limited"

    log_password_reset_attempt(email)
    return get_user_by_email(email), "ok"


def get_user_from_reset_token(token: str) -> User | None:
    """Resolve reset token to an existing user."""
    email = verify_reset_token(token)
    if not email:
        return None
    return get_user_by_email(email)


def reset_user_password(*, user: User, password: str) -> None:
    """Set and persist a user's new password."""
    user.set_password(password)
    db.session.commit()


def prepare_verification_resend(email: str) -> tuple[User | None, str]:
    """Validate and stage verification resend for a user."""
    user = get_user_by_email(email)
    if not user:
        return None, "user_not_found"
    if user.email_verified:
        return None, "already_verified"
    if is_verification_rate_limited(email):
        return None, "rate_limited"

    log_verification_attempt(email)
    generate_email_verification(user)
    db.session.commit()
    return user, "ok"


def is_password_reset_rate_limited(email: str) -> bool:
    """Check whether password reset attempts exceeded per hour."""
    one_hour_ago = datetime.now(timezone.utc) - timedelta(hours=1)
    recent_attempts = db.session.scalar(
        sa.select(sa.func.count(PasswordResetAttempt.id)).where(
            PasswordResetAttempt.email == email,
            PasswordResetAttempt.attempted_at >= one_hour_ago,
        )
    )
    return recent_attempts >= MAX_RESET_ATTEMPTS_PER_HOUR


def log_password_reset_attempt(email: str) -> None:
    """Persist password reset attempt."""
    db.session.add(PasswordResetAttempt(email=email))
    db.session.commit()


def is_verification_rate_limited(email: str) -> bool:
    """Check whether verification resend attempts exceeded per hour."""
    one_hour_ago = datetime.now(timezone.utc) - timedelta(hours=1)
    recent_attempts = db.session.scalar(
        sa.select(sa.func.count(EmailVerificationAttempt.id)).where(
            EmailVerificationAttempt.email == email,
            EmailVerificationAttempt.attempted_at >= one_hour_ago,
        )
    )
    return recent_attempts >= MAX_VERIFICATION_RESENDS_PER_HOUR


def log_verification_attempt(email: str) -> None:
    """Persist verification resend attempt."""
    db.session.add(EmailVerificationAttempt(email=email))

