def update_schedule(easiness: float, interval: int, repetitions: int, rating: int):
    """
    Update SM-2 schedule values.

    rating: 0-5 (0=Again, 3=Hard, 4=Good, 5=Easy)
    Returns: (new_easiness, new_interval, new_repetitions)
    """
    if rating < 3:
        repetitions = 0
        interval = 1
    else:
        repetitions += 1
        if repetitions == 1:
            interval = 1
        elif repetitions == 2:
            interval = 6
        else:
            interval = max(1, round(interval * easiness))

    easiness = easiness + (0.1 - (5 - rating) * (0.08 + (5 - rating) * 0.02))
    easiness = max(1.3, easiness)

    return easiness, interval, repetitions
