from .extensions import scheduler

# from .jobs.getyoutubedata import get_yt_playlist_data


# @scheduler.task("interval", id="do_yt_sync", days=1)
# def yt_sub_sync():
#     get_yt_playlist_data()


@scheduler.task("interval", id="my_test_job", seconds=10)
def my_test_job():
    print("This test job runs every 10 seconds.")
