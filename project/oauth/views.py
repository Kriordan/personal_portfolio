"""Maintainer-only authorization for the shared Library connection."""

import secrets
import time
from urllib.parse import urlsplit

import google_auth_oauthlib.flow
import requests
from flask import Blueprint, abort, current_app, flash, redirect, render_template, request, session, url_for
from flask_login import current_user
from flask_wtf import FlaskForm

from project.database import db
from project.extensions import login_manager
from project.library.credentials import (
    SCOPES, MOVE_SCOPES, YouTubeConfigurationError, credential_cipher, load_shared_credentials,
    oauth_client_config, oauth_redirect_uri, save_shared_credentials,
)
from project.models import Playlist, YouTubeConnection
from project.library.workflow import WorkflowError, channel_id, configure_workflow, connected_owner, workflow_status
from project.library.sync_tracking import assert_import_lock, import_lock

oauth_blueprint = Blueprint("oauth", __name__, template_folder="templates", url_prefix="/oauth")


@oauth_blueprint.before_request
def protect_connection():
    if not current_user.is_authenticated:
        return login_manager.unauthorized()
    if not current_user.is_admin:
        abort(403)
    # Retire the old credential-bearing browser cookie on the next visit.
    session.pop("credentials", None)
    session.pop("state", None)


def private_connection_response(response):
    if request.blueprint == "oauth":
        response.headers["Cache-Control"] = "private, no-store"
        response.headers["Referrer-Policy"] = "no-referrer"
    return response


def _connection_page(*, error=None, status=200):
    connection = db.session.get(YouTubeConnection, 1)
    configuration_error = None
    try:
        oauth_client_config()
        credential_cipher()
        callback = oauth_redirect_uri()
    except YouTubeConfigurationError as exc:
        configuration_error = str(exc)
        callback = None
    connection_url = None
    if callback and request.host != urlsplit(callback).netloc:
        parsed = urlsplit(callback)
        connection_url = f"{parsed.scheme}://{parsed.netloc}/oauth/"
    return render_template(
        "oauth/connection.html", form=FlaskForm(), connection=connection,
        error=error, configuration_error=configuration_error, connection_url=connection_url,
        workflow=workflow_status(current_user), playlists=Playlist.query.order_by(Playlist.title).all(),
    ), status


def _require_form():
    if not FlaskForm().validate_on_submit():
        abort(400, description="The form expired. Reload the connection page and try again.")


def _connection_failure(error, message):
    db.session.rollback()
    # Provider messages can contain tokens, codes, or credential-bearing URLs.
    current_app.logger.warning("YouTube connection failed (%s)", type(error).__name__)
    return _connection_page(error=message, status=503)


@oauth_blueprint.get("/")
def index():
    return _connection_page()


@oauth_blueprint.route("/authorize", methods=["GET", "POST"])
def authorize():
    if request.method == "GET":
        return redirect(url_for("oauth.index"))
    _require_form()
    upgrade = request.form.get("playlist_changes") == "yes"
    if upgrade and not connected_owner(current_user):
        abort(403)
    scopes = MOVE_SCOPES if upgrade else SCOPES
    try:
        config = oauth_client_config()
        credential_cipher()
        callback = oauth_redirect_uri()
        if request.host != urlsplit(callback).netloc:
            return _connection_page(error="Open the connection page on the website linked below.", status=400)
        flow = google_auth_oauthlib.flow.Flow.from_client_config(
            config, scopes=scopes, autogenerate_code_verifier=True,
        )
        flow.redirect_uri = callback
        authorization_url, state = flow.authorization_url(access_type="offline", prompt="consent")
        session["youtube_oauth"] = {
            "state": state, "created_at": time.time(), "user_id": current_user.id,
            "code_verifier": flow.code_verifier, "client_id": config["web"]["client_id"],
            "redirect_uri": callback,
            "scopes": scopes,
        }
        return redirect(authorization_url)
    except Exception as error:
        return _connection_failure(error, "YouTube connection could not start. Check the server configuration and retry.")


@oauth_blueprint.get("/oauth2callback")
def oauth2callback():
    pending = session.get("youtube_oauth")
    states = request.args.getlist("state")
    if (not isinstance(pending, dict) or len(states) != 1 or not states[0]
            or not isinstance(pending.get("state"), str)
            or not secrets.compare_digest(states[0].encode(), pending["state"].encode())
            or pending.get("user_id") != current_user.id
            or not isinstance(pending.get("created_at"), (int, float))
            or not 0 <= time.time() - pending["created_at"] <= 600):
        return _connection_page(error="The connection request expired or did not match. Start again.", status=400)
    # A callback is single-use, including failed exchanges and declined consent.
    session.pop("youtube_oauth", None)
    if request.args.get("error"):
        return _connection_page(error="YouTube access was not granted. The existing connection is unchanged.", status=400)
    codes = request.args.getlist("code")
    if len(codes) != 1 or not codes[0]:
        return _connection_page(error="Google did not return an authorization code. Start again.", status=400)
    try:
        config = oauth_client_config()
        callback = oauth_redirect_uri()
        if (request.host != urlsplit(callback).netloc or pending.get("redirect_uri") != callback
                or pending.get("client_id") != config["web"]["client_id"]
                or not pending.get("code_verifier")):
            return _connection_page(error="Connection settings changed. Start again.", status=400)
        scopes = pending.get("scopes", SCOPES)
        if scopes not in (SCOPES, MOVE_SCOPES):
            return _connection_page(error="Connection settings changed. Start again.", status=400)
        if scopes == MOVE_SCOPES and not connected_owner(current_user):
            abort(403)
        flow = google_auth_oauthlib.flow.Flow.from_client_config(
            config, scopes=scopes, state=pending["state"], code_verifier=pending["code_verifier"],
        )
        flow.redirect_uri = callback
        flow.fetch_token(code=codes[0], timeout=15)
        channel = None
        if scopes == MOVE_SCOPES:
            from googleapiclient.discovery import build
            from google_auth_httplib2 import AuthorizedHttp
            from httplib2 import Http
            with build("youtube", "v3", http=AuthorizedHttp(flow.credentials, http=Http(timeout=15))) as service:
                channel = channel_id(service)
        save_shared_credentials(flow.credentials, connected_by_id=current_user.id, channel_id=channel, requested_scopes=scopes)
    except Exception as error:
        return _connection_failure(error, "YouTube could not be connected. Retry and allow the requested access when Google asks. The existing connection is unchanged.")
    flash("YouTube is connected for the shared Library. Return to the app and tap Sync from YouTube.", "success")
    return redirect(url_for("oauth.index"))


@oauth_blueprint.route("/test", methods=["GET", "POST"])
def test_api_request():
    if request.method == "GET":
        return redirect(url_for("oauth.index"))
    _require_form()
    try:
        from project.library.jobs import get_youtube_service
        with get_youtube_service() as service:
            service.channels().list(part="id", mine=True, maxResults=1).execute()
    except Exception as error:
        return _connection_failure(error, "YouTube could not verify the connection. Try reconnecting; a temporary provider failure can also cause this.")
    flash("YouTube accepted the saved connection. No Library import was run.", "success")
    return redirect(url_for("oauth.index"))


@oauth_blueprint.route("/revoke", methods=["GET", "POST"])
def revoke():
    if request.method == "GET":
        return redirect(url_for("oauth.index"))
    _require_form()
    try:
        with import_lock() as acquired:
            if not acquired:
                raise WorkflowError("Library is busy.")
            connection = db.session.get(YouTubeConnection, 1)
            if connection is not None:
                credentials = load_shared_credentials()
                assert_import_lock()
                result = requests.post(
                    "https://oauth2.googleapis.com/revoke",
                    data={"token": credentials.refresh_token}, timeout=15,
                )
                result.raise_for_status()
                db.session.delete(connection)
                assert_import_lock()
                db.session.commit()
    except Exception as error:
        return _connection_failure(error, "YouTube access could not be revoked. The saved connection is unchanged.")
    session.pop("youtube_oauth", None)
    flash("YouTube access was revoked and the saved connection removed. The saved Library catalog remains available.", "success")
    return redirect(url_for("oauth.index"))


@oauth_blueprint.post("/workflow")
def save_workflow():
    _require_form()
    if not connected_owner(current_user):
        abort(403)
    try:
        configure_workflow(current_user, request.form.get("source_playlist_id", ""), request.form.get("destination_playlist_id", ""))
    except WorkflowError as error:
        db.session.rollback()
        return _connection_page(error=str(error), status=error.status)
    except Exception as error:
        return _connection_failure(error, "Couldn’t verify and save the playlists. The previous setup is unchanged. Check YouTube access and try again.")
    flash("Move to watched is configured. Return to the app and refresh the added playlist.", "success")
    return redirect(url_for("oauth.index"))


@oauth_blueprint.route("/clear", methods=["GET", "POST"])
def clear_credentials():
    # Legacy links no longer clear or replace the shared connection.
    return redirect(url_for("oauth.index"))
