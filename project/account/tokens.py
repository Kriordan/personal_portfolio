"""Token generation and verification for password reset functionality."""

from itsdangerous import URLSafeTimedSerializer, SignatureExpired, BadSignature
from flask import current_app


def generate_reset_token(email: str) -> str:
    """
    Generate a secure, time-limited password reset token.

    Args:
        email: The user's email address to encode in the token.

    Returns:
        A URL-safe token string.
    """
    serializer = URLSafeTimedSerializer(current_app.config["SECRET_KEY"])
    return serializer.dumps(email, salt="password-reset-salt")


def verify_reset_token(token: str, expiration: int = 3600) -> str | None:
    """
    Verify a password reset token and return the email if valid.

    Args:
        token: The token to verify.
        expiration: Maximum age of token in seconds (default: 1 hour).

    Returns:
        The email address if token is valid, None otherwise.
    """
    serializer = URLSafeTimedSerializer(current_app.config["SECRET_KEY"])
    try:
        email = serializer.loads(
            token, salt="password-reset-salt", max_age=expiration
        )
        return email
    except (SignatureExpired, BadSignature):
        return None

