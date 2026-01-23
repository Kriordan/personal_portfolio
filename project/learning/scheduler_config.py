from datetime import timedelta

MINUTE = 60
DAY = 60 * 60 * 24

SCHEDULER_VERSION = "sm2_v2_steps"

LEARNING_STEPS = [timedelta(minutes=10), timedelta(days=1)]
RELEARNING_STEPS = [timedelta(minutes=10), timedelta(days=1)]

GRADUATING_INTERVAL_DAYS = 3
POST_LAPSE_INTERVAL_DAYS = 1
MIN_EASINESS = 1.3
