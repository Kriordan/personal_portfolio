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
        return False

    video_status = video['status']

    if video_status.get('uploadStatus') == 'rejected':
        return False
    if video_status.get('privacyStatus') == 'private':
        return False
    if video_status.get('license') == 'youtube' and video_status.get('uploadStatus') == 'deleted':
        return False

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


def sync_playlists_and_videos(*, commit=True):
    """Import accessible items; callers can commit the catalog and receipt together.

    Counts refer to playlist entries, so one YouTube video in two playlists counts
    twice. Missing/unavailable upstream records are retained, never deleted.
    """
    service = get_youtube_service()
    playlists = {item["id"]: item for item in fetch_playlists(service)}
    summary = {kind: {key: 0 for key in ("checked", "added", "updated", "unchanged", "skipped")}
               for kind in ("playlists", "videos")}
    now = datetime.now(timezone.utc)

    def published(snippet):
        return datetime.fromisoformat(snippet["publishedAt"].replace("Z", "+00:00")).astimezone(timezone.utc).replace(tzinfo=None)

    def differs(record, values):
        for key, value in values.items():
            old = getattr(record, key)
            # PostgreSQL returns aware timestamps; SQLite returns naive ones.
            if isinstance(old, datetime):
                old = old.astimezone(timezone.utc).replace(tzinfo=None) if old.tzinfo else old
            if old != value:
                return True
        return False

    for playlist_id, item in playlists.items():
        summary["playlists"]["checked"] += 1
        snippet = item["snippet"]
        values = {"title": snippet["title"], "description": snippet.get("description"),
                  "published_at": published(snippet),
                  "thumbnail_url": snippet.get("thumbnails", {}).get("default", {}).get("url")}
        playlist = db.session.get(Playlist, playlist_id)
        created = playlist is None
        metadata_changed = not created and differs(playlist, values)
        if created:
            playlist = Playlist(id=playlist_id, **values, updated_at=now)
            db.session.add(playlist)
        elif metadata_changed:
            for key, value in values.items():
                setattr(playlist, key, value)
        changed = created or metadata_changed
        videos = {video["id"]: video for video in fetch_videos(playlist_id, service)}
        existing_videos = {record.id: record for record in Video.query.filter_by(playlist_id=playlist_id).all()}
        available_ids = set()
        for video_id, video in videos.items():
            summary["videos"]["checked"] += 1
            if not check_video_availability(video):
                summary["videos"]["skipped"] += 1
                continue
            available_ids.add(video_id)
            snippet = video["snippet"]
            position = snippet.get("position")
            values = {"title": snippet["title"], "description": snippet.get("description"),
                      "published_at": published(snippet),
                      "thumbnail_url": snippet.get("thumbnails", {}).get("default", {}).get("url"),
                      "video_url_id": video["contentDetails"]["videoId"],
                      "embed_url": f'https://www.youtube.com/embed/{video["contentDetails"]["videoId"]}',
                      "position": position if isinstance(position, int) and position >= 0 else None}
            record = existing_videos.get(video_id)
            if record is None:
                db.session.add(Video(id=video_id, playlist_id=playlist_id, **values, created_at=now, updated_at=now))
                summary["videos"]["added"] += 1
                changed = True
            elif differs(record, values):
                for key, value in values.items():
                    setattr(record, key, value)
                record.updated_at = now
                summary["videos"]["updated"] += 1
                changed = True
            else:
                summary["videos"]["unchanged"] += 1
        for video_id, record in existing_videos.items():
            if video_id not in available_ids and record.position is not None:
                # Retain saved metadata/watch history, but don't mix obsolete
                # positions into the current upstream playlist order.
                record.position = None
                changed = True
        if changed:
            playlist.updated_at = now
        summary["playlists"]["added" if created else "updated" if changed else "unchanged"] += 1
    if commit:
        db.session.commit()
    return summary
