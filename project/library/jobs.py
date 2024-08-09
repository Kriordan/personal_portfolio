import json
import logging
from datetime import datetime, timezone

import flask
import google.oauth2.credentials
from googleapiclient.discovery import build

from project.database import db
from project.models import Playlist, Video

logger = logging.getLogger(__name__)

CLIENT_SECRETS_FILE = "client_secret.json"
SCOPES = ["https://www.googleapis.com/auth/youtube.readonly"]
GOOGLE_CLIENT_API_SERVICE_NAME = "youtube"
GOOGLE_CLIENT_API_SERVICE_VERSION = "v3"


def get_youtube_service():
    """
    Returns a YouTube service object authenticated with the user's credentials.

    This function uses the Google OAuth2 library to authenticate the user and obtain
    the necessary credentials to access the YouTube API. It then creates and returns
    a YouTube service object that can be used to interact with the YouTube API.

    Returns:
        A YouTube service object.

    Raises:
        Any exceptions that may occur during the authentication process.
    """
    print('Building YouTube service object')
    if "credentials" not in flask.session:
        return flask.redirect("authorize")

    credentials = google.oauth2.credentials.Credentials(**flask.session["credentials"])
    return build(
        GOOGLE_CLIENT_API_SERVICE_NAME,
        GOOGLE_CLIENT_API_SERVICE_VERSION,
        credentials=credentials,
    )


def fetch_playlists(youtube_service):
    """
    Fetches playlists from YouTube using the YouTube Data API.

    Returns:
        A list of playlists retrieved from YouTube.
    """
    playlists = []

    with open("project/data/jsonfiles/youtube-ids.json", "r", encoding="utf-8") as f:
        playlist_ids = json.load(f)

    print("""
    ##########################
    Fetching created playlists
    ##########################
    """)

    request = youtube_service.playlists().list(  # pylint: disable=no-member
        part="snippet,contentDetails", mine=True, maxResults=50
    )
    while request is not None:
        response = request.execute()
        playlists.extend(response.get("items", []))
        request = youtube_service.playlists().list_next(  # pylint: disable=no-member
            request, response
        )

    print("""
    ##########################
    Fetching saved playlists
    ##########################
    """)

    for playlist_id in playlist_ids:
        request = youtube_service.playlists().list(  # pylint: disable=no-member
            part="snippet,contentDetails", id=playlist_id
        )
        response = request.execute()
        playlists.extend(response.get("items", []))

    return playlists


def fetch_videos(playlist_id, youtube_service):
    """
    Fetches videos from a YouTube playlist.

    Args:
        playlist_id (str): The ID of the YouTube playlist.

    Returns:
        list: A list of video items from the playlist.
    """
    videos = []

    print(f'Fetching videos for Playlist {playlist_id}')
    request = youtube_service.playlistItems().list(  # pylint: disable=no-member
        part="snippet,contentDetails,status", playlistId=playlist_id, maxResults=50
    )
    while request is not None:
        response = request.execute()
        videos.extend(response.get("items", []))
        request = youtube_service.playlistItems().list_next(  # pylint: disable=no-member
            request, response
        )

    return videos

def check_video_availability(video):
    if video['snippet']['title'] == 'Deleted video' or video['snippet']['description'] == 'This video is unavailable':
        print(f'Video {video['id']} is unavailable or has been deleted.')
        return False

    video_status = video['status']

    if video_status.get('uploadStatus') == 'rejected':
        print(f"Video {video['id']} was rejected.")
        return False
    if video_status.get('privacyStatus') == 'private':
        print(f"Video {video['id']} is private.")
        return False
    if video_status.get('license') == 'youtube' and video_status.get('uploadStatus') == 'deleted':
        print(f"Video {video['id']} has been deleted.")
        return False

    print(f"Video {video['id']} is available.")
    return True


def sync_playlists_and_videos():
    """
    Synchronizes playlists and videos from YouTube.

    This function fetches playlists from YouTube and updates the corresponding
    records in the database. For each playlist, it checks if the playlist
    already exists in the database. If it does, it compares the playlist
    details (title, description, published date, thumbnail URL) with the
    fetched data and updates the database record if there are any changes. If
    the playlist doesn't exist in the database, a new record is created.

    After updating or creating the playlist record, the function fetches the
    videos for that playlist and performs a similar check and update process
    for each video. If a video already exists in the database, it compares the
    video details (title, description, published date, thumbnail URL, embed
    URL) with the fetched data and updates the database record if there are any
    changes. If the video doesn't exist in the database, a new record is
    created.

    Finally, if any changes were made to the playlist or its videos, the
    `updated_at` field of the playlist record is updated and the changes are
    committed to the database.

    Returns:
        None

    Raises:
        None
    """
    service = get_youtube_service()
    playlists = fetch_playlists(service)

    for playlist in playlists:
        print(f"Processing playlist {playlist["id"]}")
        playlist_id = playlist["id"]
        title = playlist["snippet"]["title"]
        description = playlist["snippet"].get("description")
        published_at = datetime.strptime(
            playlist["snippet"]["publishedAt"], "%Y-%m-%dT%H:%M:%SZ"
        )
        thumbnail_url = playlist["snippet"].get("thumbnails", {}).get("default", {}).get("url")

        existing_playlist = Playlist.query.get(playlist_id)
        playlist_updated = False
        if existing_playlist:
            if (
                existing_playlist.title != title
                or existing_playlist.description != description
                or existing_playlist.published_at != published_at
                or existing_playlist.thumbnail_url != thumbnail_url
            ):
                existing_playlist.title = title
                existing_playlist.description = description
                existing_playlist.published_at = published_at
                existing_playlist.thumbnail_url = thumbnail_url
                playlist_updated = True
                print(f"Playlist {playlist["id"]} updated")
        else:
            new_playlist = Playlist(
                id=playlist_id,
                title=title,
                description=description,
                published_at=published_at,
                updated_at=datetime.now(timezone.utc),
                thumbnail_url=thumbnail_url,
            )
            db.session.add(new_playlist)
            playlist_updated = True
            print(f"Playlist {playlist["id"]} created")

        videos = fetch_videos(playlist_id, service)
        for video in videos:
            print(f"Processing video {video["id"]}")

            if not check_video_availability(video):
                continue

            video_id = video["id"]
            video_url_id = video["contentDetails"]["videoId"]
            video_title = video["snippet"]["title"]
            video_description = video["snippet"].get("description")
            video_published_at = datetime.strptime(
                video["snippet"]["publishedAt"], "%Y-%m-%dT%H:%M:%SZ"
            )
            video_thumbnail_url = (
                video["snippet"].get("thumbnails", {}).get("default", {}).get("url")
            )
            embed_url = f"https://www.youtube.com/embed/{video_url_id}"

            existing_video = Video.query.get(video_id)
            if existing_video:
                if (
                    existing_video.title != video_title
                    or existing_video.description != video_description
                    or existing_video.published_at != video_published_at
                    or existing_video.thumbnail_url != video_thumbnail_url
                    or existing_video.video_url_id != video_url_id
                    or existing_video.embed_url != embed_url
                ):
                    existing_video.title = video_title
                    existing_video.description = video_description
                    existing_video.published_at = video_published_at
                    existing_video.thumbnail_url = video_thumbnail_url
                    existing_video.video_url_id = video_url_id
                    existing_video.embed_url = embed_url
                    existing_video.updated_at = datetime.now(timezone.utc)
                    playlist_updated = True
                    print(f"Video {video["id"]} updated")
            else:
                new_video = Video(
                    id=video_id,
                    playlist_id=playlist_id,
                    video_url_id=video_url_id,
                    title=video_title,
                    description=video_description,
                    published_at=video_published_at,
                    thumbnail_url=video_thumbnail_url,
                    embed_url=embed_url,
                    created_at=datetime.now(timezone.utc),
                    updated_at=datetime.now(timezone.utc),
                )
                db.session.add(new_video)
                playlist_updated = True
                print(f"Video {video["id"]} created")

        if playlist_updated and existing_playlist:
            existing_playlist.updated_at = datetime.now(timezone.utc)

    db.session.commit()
    logger.info("YouTube playlists and videos synchronized successfully.")
