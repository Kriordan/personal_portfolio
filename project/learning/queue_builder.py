import random


def _top_tag(card):
    tags = card.get("tags") or []
    return tags[0] if tags else None


def _score_card(card, progress, rng):
    lapses = progress.lapses if progress else 0
    interval = progress.interval if progress else 1
    learning_state = progress.learning_state if progress else "new"
    state_weight = {
        "relearning": 2,
        "learning": 1,
        "new": 1,
        "review": 0,
    }.get(learning_state, 0)
    recent_lapse_bonus = 50 if progress and progress.last_rating is not None else 0
    if progress and progress.last_rating is not None and progress.last_rating < 3:
        recent_lapse_bonus = 75
    return (lapses * 100) + (state_weight * 10) + recent_lapse_bonus - interval + rng.random()


def _violates_constraints(card, queue, enforce_note, enforce_tag):
    if enforce_note and len(queue) >= 2:
        if queue[-1]["note_id"] == queue[-2]["note_id"] == card["note_id"]:
            return True

    if enforce_tag:
        candidate_tag = _top_tag(card)
        if candidate_tag and len(queue) >= 3:
            recent_tags = [_top_tag(item) for item in queue[-3:]]
            if all(tag == candidate_tag for tag in recent_tags):
                return True

    return False


def build_review_queue(due_cards, progress_map, seed=None):
    rng = random.Random(seed)
    scored = []
    for card in due_cards:
        progress = progress_map.get(card["card_id"])
        scored.append((card, _score_card(card, progress, rng)))
    scored.sort(key=lambda pair: pair[1], reverse=True)
    remaining = [pair[0] for pair in scored]

    queue = []
    while remaining:
        selected = None
        for card in remaining:
            if not _violates_constraints(card, queue, True, True):
                selected = card
                break
        if selected is None:
            for card in remaining:
                if not _violates_constraints(card, queue, True, False):
                    selected = card
                    break
        if selected is None:
            selected = remaining[0]

        queue.append(selected)
        remaining.remove(selected)

    return queue
