import json
import logging
from datetime import datetime, timezone

from googleapiclient.discovery import build

from project.database import db
from project.library.credentials import YouTubeConfigurationError, load_shared_credentials
from project.models import Playlist, Video

logger = logging.getLogger(__name__)

def get_youtube_service():
    """Use the maintainer's shared, durable connection for API, website, and CLI."""
    return build("youtube", "v3", credentials=load_shared_credentials())


def fetch_playlists(youtube_service):
    """
    Fetches playlists from YouTube using the YouTube Data API.

    Returns:
        A list of playlists retrieved from YouTube.
    """
    playlists = []

    try:
        with open("project/data/jsonfiles/youtube-ids.json", "r", encoding="utf-8") as f:
            playlist_ids = json.load(f)
        if not isinstance(playlist_ids, list) or not all(isinstance(value, str) for value in playlist_ids):
            raise ValueError("Expected playlist IDs")
    except (OSError, ValueError) as error:
        raise YouTubeConfigurationError("YouTube playlist configuration unavailable.") from error

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


def fetch_subscriptions(youtube_service):
    """
    Fetches all YouTube channel subscriptions for the authenticated user.

    Args:
        youtube_service: Authenticated YouTube API service object.

    Returns:
        list: A list of subscription items containing channel information.
    """
    subscriptions = []

    print("""
    ##########################
    Fetching subscriptions
    ##########################
    """)

    try:
        request = youtube_service.subscriptions().list(  # pylint: disable=no-member
            part="snippet,contentDetails", mine=True, maxResults=50
        )
        
        while request is not None:
            print(f"Making API request... (currently have {len(subscriptions)} subscriptions)")
            response = request.execute()
            items = response.get("items", [])
            print(f"Received {len(items)} items in this batch")
            subscriptions.extend(items)
            request = youtube_service.subscriptions().list_next(  # pylint: disable=no-member
                request, response
            )
        
        print(f"Fetched {len(subscriptions)} total subscriptions")
        return subscriptions
    except Exception as e:
        print(f"ERROR fetching subscriptions: {str(e)}")
        logger.error(f"Error fetching subscriptions: {str(e)}")
        raise


def export_subscriptions_to_json():
    """
    Fetches YouTube channel subscriptions and exports them to a JSON file.

    This function retrieves all channels the authenticated user is subscribed to
    and saves the data to 'project/data/jsonfiles/youtube-subscriptions.json'.

    The exported data includes:
    - Channel ID
    - Channel title
    - Description
    - Thumbnail URL
    - Published date (when subscription was created)
    - Total upload count

    Returns:
        dict: A dictionary containing the subscription data and metadata.

    Raises:
        Any exceptions that may occur during the API call or file write.
    """
    try:
        print("Getting YouTube service...")
        service = get_youtube_service()
        
        print("Fetching subscriptions...")
        subscriptions = fetch_subscriptions(service)
        
        print(f"Processing {len(subscriptions)} subscriptions...")
        # Format the data for export
        formatted_subscriptions = []
        for i, sub in enumerate(subscriptions):
            try:
                channel_info = {
                    "channel_id": sub["snippet"]["resourceId"]["channelId"],
                    "channel_title": sub["snippet"]["title"],
                    "description": sub["snippet"].get("description", ""),
                    "thumbnail_url": sub["snippet"].get("thumbnails", {}).get("default", {}).get("url"),
                    "subscribed_at": sub["snippet"]["publishedAt"],
                    "total_item_count": sub["contentDetails"].get("totalItemCount", 0),
                }
                formatted_subscriptions.append(channel_info)
            except Exception as e:
                print(f"Error processing subscription {i}: {str(e)}")
                logger.error(f"Error processing subscription {i}: {str(e)}")
                continue

        # Create output dictionary with metadata
        output_data = {
            "fetched_at": datetime.now(timezone.utc).isoformat(),
            "total_subscriptions": len(formatted_subscriptions),
            "subscriptions": formatted_subscriptions,
        }

        # Write to JSON file
        output_path = "project/data/jsonfiles/youtube-subscriptions.json"
        print(f"Writing to {output_path}...")
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(output_data, f, indent=2, ensure_ascii=False)

        print(f"Successfully exported {len(formatted_subscriptions)} subscriptions to {output_path}")
        logger.info(f"Exported {len(formatted_subscriptions)} YouTube subscriptions to {output_path}")
        
        return output_data
    except Exception as e:
        print(f"ERROR in export_subscriptions_to_json: {str(e)}")
        logger.error(f"Error in export_subscriptions_to_json: {str(e)}")
        raise


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
        published_at = datetime.fromisoformat(
            playlist["snippet"]["publishedAt"].replace("Z", "+00:00")
        ).replace(tzinfo=None)
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
            video_published_at = datetime.fromisoformat(
                video["snippet"]["publishedAt"].replace("Z", "+00:00")
            ).replace(tzinfo=None)
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
