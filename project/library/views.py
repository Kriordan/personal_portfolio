# Python

from flask import Blueprint, flash, redirect, render_template, url_for
from flask_login import login_required

from project.library.jobs import export_subscriptions_to_json, sync_playlists_and_videos
from project.models import Playlist, Video

library_blueprint = Blueprint(
    "library", __name__, template_folder="templates", url_prefix="/lib"
)


@library_blueprint.route("/", methods=["GET"])
@login_required
def library_home():
    """Renders the library.html template."""
    playlists = Playlist.query.all()

    return render_template("playlists.html", playlists=playlists)


@library_blueprint.route("/playlist/<playlist_id>", methods=["GET"])
@login_required
def view_playlist(playlist_id):
    """Renders the library.html template."""
    playlist = Playlist.query.get(playlist_id)
    videos = Video.query.filter_by(playlist_id=playlist_id).all()

    return render_template("playlist.html", playlist=playlist, videos=videos)


@library_blueprint.route("/videos/<video_id>")
@login_required
def view_video(video_id):
    video = Video.query.get(video_id)

    return render_template("video.html", video=video)


@library_blueprint.route("/sync_playlists", methods=["POST"])
@login_required
def sync_playlists():
    """Synchronizes playlists and videos."""
    sync_playlists_and_videos()

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
