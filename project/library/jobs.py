import json
import logging
import os
from datetime import datetime, timezone

from googleapiclient.discovery import build

from project.database import db
from project.models import Playlist, Video

logger = logging.getLogger(__name__)


def get_youtube_service():
    api_key = os.getenv("GOOGLE_API_KEY")
    return build("youtube", "v3", developerKey=api_key)


def fetch_playlists():
    service = get_youtube_service()
    playlists = []

    # Load playlist IDs from JSON file
    with open("project/data/jsonfiles/youtube-ids.json", "r", encoding="utf-8") as f:
        playlist_ids = json.load(f)

    # Fetch playlists from YouTube API
    request = service.playlists().list(
        part="snippet,contentDetails", mine=True, maxResults=50
    )
    while request is not None:
        response = request.execute()
        playlists.extend(response.get("items", []))
        request = service.playlists().list_next(request, response)

    # Fetch details for each playlist ID from JSON file
    for playlist_id in playlist_ids:
        request = service.playlists().list(
            part="snippet,contentDetails", id=playlist_id
        )
        response = request.execute()
        playlists.extend(response.get("items", []))

    return playlists


def fetch_videos(playlist_id):
    service = get_youtube_service()
    videos = []

    request = service.playlistItems().list(
        part="snippet,contentDetails", playlistId=playlist_id, maxResults=50
    )
    while request is not None:
        response = request.execute()
        videos.extend(response.get("items", []))
        request = service.playlistItems().list_next(request, response)

    return videos


def sync_playlists_and_videos():
    playlists = fetch_playlists()

    for playlist in playlists:
        playlist_id = playlist["id"]
        title = playlist["snippet"]["title"]
        description = playlist["snippet"].get("description")
        published_at = datetime.strptime(
            playlist["snippet"]["publishedAt"], "%Y-%m-%dT%H:%M:%SZ"
        )
        thumbnail_url = playlist["snippet"]["thumbnails"]["default"]["url"]

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

        videos = fetch_videos(playlist_id)
        for video in videos:
            video_id = video["contentDetails"]["videoId"]
            video_title = video["snippet"]["title"]
            video_description = video["snippet"].get("description")
            video_published_at = datetime.strptime(
                video["snippet"]["publishedAt"], "%Y-%m-%dT%H:%M:%SZ"
            )
            video_thumbnail_url = video["snippet"]["thumbnails"]["default"]["url"]
            embed_url = f"https://www.youtube.com/embed/{video_id}"

            existing_video = Video.query.get(video_id)
            if existing_video:
                if (
                    existing_video.title != video_title
                    or existing_video.description != video_description
                    or existing_video.published_at != video_published_at
                    or existing_video.thumbnail_url != video_thumbnail_url
                    or existing_video.embed_url != embed_url
                ):
                    existing_video.title = video_title
                    existing_video.description = video_description
                    existing_video.published_at = video_published_at
                    existing_video.thumbnail_url = video_thumbnail_url
                    existing_video.embed_url = embed_url
                    existing_video.updated_at = datetime.now(timezone.utc)
                    playlist_updated = True
            else:
                new_video = Video(
                    id=video_id,
                    playlist_id=playlist_id,
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

        if playlist_updated and existing_playlist:
            existing_playlist.updated_at = datetime.now(timezone.utc)

    db.session.commit()
    logger.info("YouTube playlists and videos synchronized successfully.")
