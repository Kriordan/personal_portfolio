from project.library.jobs import sync_playlists_and_videos

from .extensions import scheduler

# @scheduler.task("interval", id="my_test_job", seconds=10)
# def my_test_job():
#     print("This test job runs every 10 seconds.")


# @scheduler.task("interval", id="sync_yt_subs", hours=24)
# def sync_yt_subs():
#     sync_playlists_and_videos()
