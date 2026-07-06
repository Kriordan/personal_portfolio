from flask import Blueprint, flash, redirect, render_template, url_for
from flask_login import login_required

from project.library.jobs import export_subscriptions_to_json
from project.services import library_service

library_blueprint = Blueprint(
    "library", __name__, template_folder="templates", url_prefix="/lib"
)


@library_blueprint.route("/", methods=["GET"])
@login_required
def library_home():
    """Renders the playlists overview."""
    playlists = library_service.list_playlists()

    return render_template("playlists.html", playlists=playlists)


@library_blueprint.route("/playlist/<playlist_id>", methods=["GET"])
@login_required
def view_playlist(playlist_id):
    """Renders a single playlist with its videos."""
    try:
        playlist, videos = library_service.get_playlist_with_videos(playlist_id=playlist_id)
    except library_service.NotFoundError:
        return render_template("404.html"), 404

    return render_template("playlist.html", playlist=playlist, videos=videos)


@library_blueprint.route("/videos/<video_id>")
@login_required
def view_video(video_id):
    try:
        video = library_service.get_video(video_id=video_id)
    except library_service.NotFoundError:
        return render_template("404.html"), 404

    return render_template("video.html", video=video)


@library_blueprint.route("/sync_playlists", methods=["POST"])
@login_required
def sync_playlists():
    """Synchronizes playlists and videos."""
    library_service.sync_library()

    return redirect(url_for("foyer.utilities"))


@library_blueprint.route("/export_subscriptions", methods=["POST"])
@login_required
def export_subscriptions():
    """Exports YouTube channel subscriptions to a JSON file."""
    try:
        result = export_subscriptions_to_json()
        flash(
            f"Successfully exported {result['total_subscriptions']} subscriptions to youtube-subscriptions.json",
            "success",
        )
    except ValueError as e:
        # Handle authentication errors
        if "credentials not found" in str(e).lower():
            flash(
                "YouTube authorization required. Please authorize the app first.",
                "error",
            )
            return redirect(url_for("oauth.authorize"))
        flash(f"Error: {str(e)}", "error")
    except Exception as e:
        flash(f"Error exporting subscriptions: {str(e)}", "error")

    return redirect(url_for("foyer.utilities"))
