"""
This module handles OAuth 2.0 authentication
"""

# -*- coding: utf-8 -*-
import json

import flask
import google.oauth2.credentials
import google_auth_oauthlib.flow
import googleapiclient.discovery
import requests
from flask import Blueprint

oauth_blueprint = Blueprint(
    "oauth", __name__, template_folder="templates", url_prefix="/oauth"
)

CLIENT_SECRETS_FILE = "client_secret.json"

# This OAuth 2.0 access scope allows for full read/write access to the
# authenticated user's account and requires requests to use an SSL connection.
SCOPES = ["https://www.googleapis.com/auth/youtube.readonly"]
GOOGLE_CLIENT_API_SERVICE_NAME = "youtube"
GOOGLE_CLIENT_API_SERVICE_VERSION = "v3"


@oauth_blueprint.route("/")
def index():
    """
    This function returns the index table by calling the print_index_table function.
    """
    return print_index_table()


@oauth_blueprint.route("/test")
def test_api_request():
    """
    This function sends an API request to the YouTube Data API to fetch channel
    details and playlists.
    It requires the user to have authorized the application and stored the credentials
    in the session.

    Returns:
        A JSON response containing the fetched playlists details.
    """
    if "credentials" not in flask.session:
        return flask.redirect("authorize")

    credentials = google.oauth2.credentials.Credentials(**flask.session["credentials"])

    youtube_service = googleapiclient.discovery.build(
        GOOGLE_CLIENT_API_SERVICE_NAME,
        GOOGLE_CLIENT_API_SERVICE_VERSION,
        credentials=credentials,
    )
    print_channel_details(youtube_service)
    playlists = fetch_playlists_details(youtube_service)

    # Save credentials back to session in case access token was refreshed.
    # ACTION ITEM: In a production app, you likely want to save these
    #              credentials in a persistent database instead.
    flask.session["credentials"] = credentials_to_dict(credentials)

    if not isinstance(playlists, dict):
        playlists = {"playlists": playlists}

    return flask.jsonify(**playlists)


def print_channel_details(youtube_service):
    """
    Prints the details of the authenticated user's YouTube channel.

    Args:
        youtube_service: An instance of the YouTube service.

    Returns:
        None
    """
    channel_request = youtube_service.channels().list(
        part="snippet,contentDetails,statistics", mine=True
    )
    channel_response = channel_request.execute()

    for item in channel_response["items"]:
        print("Channel Title:", item["snippet"]["title"])
        print("Channel ID:", item["id"])
        print("Description:", item["snippet"]["description"])
        print("Subscribers:", item["statistics"]["subscriberCount"])
        print("Total Views:", item["statistics"]["viewCount"])
        print("-" * 50)


def fetch_playlists_details(youtube_service):
    """
    Fetches details of playlists from the YouTube service.

    Args:
        youtube_service: The YouTube service object.

    Returns:
        A list of playlist details.
    """
    playlists = []

    playlist_request = youtube_service.playlists().list(
        part="snippet,contentDetails",
        mine=True,
        maxResults=50,
    )
    playlist_response = playlist_request.execute()
    playlists.extend(playlist_response.get("items", []))

    with open("project/data/jsonfiles/youtube-ids.json", "r", encoding="utf-8") as f:
        playlist_ids = json.load(f)

    for playlist_id in playlist_ids:
        request = youtube_service.playlists().list(
            part="snippet,contentDetails", id=playlist_id
        )
        response = request.execute()
        playlists.extend(response.get("items", []))

    return playlists


@oauth_blueprint.route("/authorize")
def authorize():
    """
    Initiates the OAuth 2.0 Authorization Grant Flow for the application.

    Returns:
        A redirect response to the authorization URL.
    """
    # Create flow instance to manage the OAuth 2.0 Authorization Grant Flow steps.
    flow = google_auth_oauthlib.flow.Flow.from_client_secrets_file(
        CLIENT_SECRETS_FILE, scopes=SCOPES
    )

    # The URI created here must exactly match one of the authorized redirect URIs
    # for the OAuth 2.0 client, which you configured in the API Console. If this
    # value doesn't match an authorized URI, you will get a 'redirect_uri_mismatch'
    # error.
    flow.redirect_uri = flask.url_for("oauth.oauth2callback", _external=True)

    authorization_url, state = flow.authorization_url(
        # Enable offline access so that you can refresh an access token without
        # re-prompting the user for permission. Recommended for web server apps.
        access_type="offline",
        # Enable incremental authorization. Recommended as a best practice.
        include_granted_scopes="true",
    )

    # Store the state so the callback can verify the auth server response.
    flask.session["state"] = state

    return flask.redirect(authorization_url)


@oauth_blueprint.route("/oauth2callback")
def oauth2callback():
    """
    Callback function for handling OAuth 2.0 authorization response.

    This function is responsible for fetching the OAuth 2.0 tokens from the
    authorization server's response and storing the credentials in the session.

    Returns:
        A redirect response to the "oauth.test_api_request" endpoint.
    """
    # Specify the state when creating the flow in the callback so that it can
    # be verified in the authorization server response.
    state = flask.session["state"]

    flow = google_auth_oauthlib.flow.Flow.from_client_secrets_file(
        CLIENT_SECRETS_FILE, scopes=SCOPES, state=state
    )
    flow.redirect_uri = flask.url_for("oauth.oauth2callback", _external=True)

    # Use the authorization server's response to fetch the OAuth 2.0 tokens.
    authorization_response = flask.request.url
    flow.fetch_token(authorization_response=authorization_response)

    # Store credentials in the session.
    # ACTION ITEM: In a production app, you likely want to save these
    #              credentials in a persistent database instead.
    credentials = flow.credentials
    flask.session["credentials"] = credentials_to_dict(credentials)

    return flask.redirect(flask.url_for("oauth.test_api_request"))


@oauth_blueprint.route("/revoke")
def revoke():
    """
    Revoke the credentials for the current user.

    If the user has not authorized the application, a message is returned
    prompting the user to authorize before testing the code to revoke credentials.

    Returns:
        str: A message indicating whether the credentials were successfully revoked
        or if an error occurred.
    """
    if "credentials" not in flask.session:
        return (
            'You need to <a href="/authorize">authorize</a> before '
            + "testing the code to revoke credentials."
        )

    credentials = google.oauth2.credentials.Credentials(**flask.session["credentials"])

    revoke = requests.post(
        "https://oauth2.googleapis.com/revoke",
        params={"token": credentials.token},
        headers={"content-type": "application/x-www-form-urlencoded"},
        timeout=10,
    )

    status_code = getattr(revoke, "status_code")
    if status_code == 200:
        return "Credentials successfully revoked." + print_index_table()
    else:
        return "An error occurred." + print_index_table()


@oauth_blueprint.route("/clear")
def clear_credentials():
    """
    Clears the credentials stored in the session.

    Returns:
        str: A message indicating that the credentials have been cleared.
    """
    if "credentials" in flask.session:
        del flask.session["credentials"]
    return "Credentials have been cleared.<br><br>" + print_index_table()


def credentials_to_dict(credentials):
    """
    Converts the given credentials object to a dictionary.

    Args:
        credentials: An object containing the credentials information.

    Returns:
        A dictionary containing the token, refresh_token, token_uri, client_id,
        client_secret, and scopes from the credentials object.
    """
    return {
        "token": credentials.token,
        "refresh_token": credentials.refresh_token,
        "token_uri": credentials.token_uri,
        "client_id": credentials.client_id,
        "client_secret": credentials.client_secret,
        "scopes": credentials.scopes,
    }


def print_index_table():
    """
    Returns an HTML table containing links and descriptions for different API requests.

    Returns:
        str: HTML table containing links and descriptions.
    """
    return (
        "<table>"
        + '<tr><td><a href="/test">Test an API request</a></td>'
        + "<td>Submit an API request and see a formatted JSON response. "
        + "    Go through the authorization flow if there are no stored "
        + "    credentials for the user.</td></tr>"
        + '<tr><td><a href="/authorize">Test the auth flow directly</a></td>'
        + "<td>Go directly to the authorization flow. If there are stored "
        + "    credentials, you still might not be prompted to reauthorize "
        + "    the application.</td></tr>"
        + '<tr><td><a href="/revoke">Revoke current credentials</a></td>'
        + "<td>Revoke the access token associated with the current user "
        + "    session. After revoking credentials, if you go to the test "
        + "    page, you should see an <code>invalid_grant</code> error."
        + "</td></tr>"
        + '<tr><td><a href="/clear">Clear Flask session credentials</a></td>'
        + "<td>Clear the access token currently stored in the user session. "
        + '    After clearing the token, if you <a href="/test">test the '
        + "    API request</a> again, you should go back to the auth flow."
        + "</td></tr></table>"
    )
