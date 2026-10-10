"""The shared Library's durable, server-only YouTube connection."""

from datetime import datetime, timezone
from urllib.parse import urlsplit

from cryptography.fernet import Fernet, InvalidToken
from flask import current_app
from google.oauth2.credentials import Credentials

from project.database import db
from project.models import YouTubeConnection

SCOPES = ["https://www.googleapis.com/auth/youtube.readonly"]
TOKEN_URI = "https://oauth2.googleapis.com/token"


class YouTubeConfigurationError(ValueError):
    """Connection setup needs maintainer attention; never include secret values."""


def credential_cipher() -> Fernet:
    key = current_app.config.get("YOUTUBE_CREDENTIALS_KEY")
    if not key:
        raise YouTubeConfigurationError("YouTube credential encryption is not configured.")
    try:
        return Fernet(key)
    except (TypeError, ValueError) as error:
        raise YouTubeConfigurationError("YouTube credential encryption is not configured.") from error


def oauth_client_config() -> dict:
    client_id = current_app.config.get("GOOGLE_CLIENT_ID")
    client_secret = current_app.config.get("GOOGLE_CLIENT_SECRET")
    if not client_id or not client_secret:
        raise YouTubeConfigurationError("YouTube OAuth client is not configured.")
    return {"web": {
        "client_id": client_id,
        "client_secret": client_secret,
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": TOKEN_URI,
    }}


def oauth_redirect_uri() -> str:
    uri = current_app.config.get("YOUTUBE_OAUTH_REDIRECT_URI", "")
    try:
        parsed = urlsplit(uri)
        parsed.port  # Validate a configured port before using the callback.
    except (TypeError, ValueError) as error:
        raise YouTubeConfigurationError("YouTube OAuth callback is not configured.") from error
    if (parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password
            or parsed.query or parsed.fragment or parsed.path != "/oauth/oauth2callback"):
        raise YouTubeConfigurationError("YouTube OAuth callback is not configured.")
    return uri


def save_shared_credentials(credentials, *, connected_by_id: int) -> None:
    """Replace the shared connection only after a complete offline-access grant."""
    config = oauth_client_config()["web"]
    if credentials.client_id != config["client_id"] or not credentials.refresh_token:
        raise YouTubeConfigurationError("Google did not provide the required offline access. Reconnect YouTube.")
    granted = credentials.granted_scopes
    if granted is not None and not set(SCOPES).issubset(granted):
        raise YouTubeConfigurationError("YouTube read access was not granted. Reconnect YouTube.")
    encrypted = credential_cipher().encrypt(credentials.refresh_token.encode()).decode()
    connection = db.session.get(YouTubeConnection, 1)
    if connection is None:
        connection = YouTubeConnection(id=1)
        db.session.add(connection)
    connection.encrypted_refresh_token = encrypted
    connection.oauth_client_id = config["client_id"]
    connection.connected_by_id = connected_by_id
    connection.connected_at = datetime.now(timezone.utc)
    db.session.commit()


def load_shared_credentials() -> Credentials:
    connection = db.session.get(YouTubeConnection, 1)
    if connection is None:
        raise YouTubeConfigurationError("YouTube is not connected.")
    config = oauth_client_config()["web"]
    if connection.oauth_client_id != config["client_id"]:
        raise YouTubeConfigurationError("The YouTube OAuth client changed. Reconnect YouTube.")
    try:
        refresh_token = credential_cipher().decrypt(connection.encrypted_refresh_token.encode()).decode()
    except (InvalidToken, UnicodeError, TypeError, ValueError) as error:
        raise YouTubeConfigurationError("The saved YouTube connection cannot be opened. Reconnect YouTube.") from error
    # Start without an access token. Google's transport obtains one from the
    # durable refresh token; no expired access token or browser cookie is reused.
    return Credentials(
        token=None, refresh_token=refresh_token, token_uri=TOKEN_URI,
        client_id=config["client_id"], client_secret=config["client_secret"], scopes=SCOPES,
    )
