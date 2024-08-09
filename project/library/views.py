# Python

from flask import Blueprint, redirect, render_template, url_for
from flask_login import login_required

from project.library.jobs import sync_playlists_and_videos
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
