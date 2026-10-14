"""Disposable YouTube double for tests/previews. Never contacts Google."""
from copy import deepcopy
from datetime import datetime, timezone


def item(entry_id, playlist_id, video_id="fixture-video", title="Fixture video", position=0):
    return {"id": entry_id, "snippet": {"playlistId": playlist_id, "title": title,
        "description": "Disposable fixture", "publishedAt": "2026-10-10T12:00:00Z", "position": position,
        "resourceId": {"kind": "youtube#video", "videoId": video_id}},
        "contentDetails": {"videoId": video_id}, "status": {"privacyStatus": "public"}}


class Request:
    def __init__(self, action):
        self.action = action

    def execute(self, **kwargs):
        return deepcopy(self.action())


class LibraryFixtureProvider:
    def __init__(self):
        self.channel = "fixture-channel"
        self.playlist_data = {name: {"id": name, "snippet": {"title": title, "channelId": self.channel,
            "publishedAt": "2026-01-01T12:00:00Z", "description": "Fixture playlist"}}
            for name, title in [("PLadded", "watch later - added"), ("PLwatched", "watch later - watched"), ("PLother", "Other videos")]}
        self.items = {"source-entry": item("source-entry", "PLadded")}
        self.events = []
        self.insert_failure = None
        self.delete_failure = None
        self.fail_after_insert = False
        self.fail_after_delete = False
        self.read_failure = None
        self.delay = 0

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def channels(self):
        provider = self
        class Channels:
            def list(self, **kwargs):
                return Request(lambda: {"items": [{"id": provider.channel}]})
        return Channels()

    def playlists(self):
        provider = self
        class Playlists:
            def list(self, **kwargs):
                return Request(lambda: {"items": [value for key, value in provider.playlist_data.items() if "id" not in kwargs or key in kwargs["id"].split(",")]})

            def list_next(self, request, response):
                return None
        return Playlists()

    def playlistItems(self):
        provider = self
        class Items:
            def list(self, **kwargs):
                def read():
                    provider.events.append(("read", kwargs))
                    if provider.read_failure:
                        raise provider.read_failure
                    return {"items": [value for key, value in provider.items.items()
                        if ("id" not in kwargs or key == kwargs["id"])
                        and ("playlistId" not in kwargs or value["snippet"]["playlistId"] == kwargs["playlistId"])
                        and ("videoId" not in kwargs or value["contentDetails"]["videoId"] == kwargs["videoId"])]}
                return Request(read)

            def list_next(self, request, response):
                return None

            def insert(self, **kwargs):
                def insert():
                    import time
                    provider.events.append(("insert", kwargs))
                    if provider.delay:
                        time.sleep(provider.delay)
                    if provider.insert_failure and not provider.fail_after_insert:
                        raise provider.insert_failure
                    snippet = kwargs["body"]["snippet"]
                    entry_id = f"destination-{len(provider.items)}"
                    value = item(entry_id, snippet["playlistId"], snippet["resourceId"]["videoId"])
                    provider.items[entry_id] = value
                    if provider.insert_failure:
                        raise provider.insert_failure
                    return value
                return Request(insert)

            def delete(self, **kwargs):
                def delete():
                    provider.events.append(("delete", kwargs))
                    if provider.delete_failure and not provider.fail_after_delete:
                        raise provider.delete_failure
                    provider.items.pop(kwargs["id"], None)
                    if provider.delete_failure:
                        raise provider.delete_failure
                    return None
                return Request(delete)
        return Items()
