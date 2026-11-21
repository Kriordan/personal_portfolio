"""Deterministic legacy notes shared by the hub route and browser regressions."""
from datetime import datetime, timedelta, timezone
import json

from project.database import db
from project.models import ReviewProgress


def seed_notes(directory):
    directory.mkdir(exist_ok=True)
    for number in range(30):
        note_id = f"hub-{number:02}"
        title = f"Note {number:02}: retries and recovery"
        if number == 29:
            title = 'Note 29: <script>alert("title")</script> ' + "long-title" * 12
        (directory / f"{note_id}.json").write_text(json.dumps(dict(
            id=note_id, title=title, flashcards=[dict(id="q", question=f"Question {number:02}",
                                                   answer=f"Private answer {number:02}")])))
    now = datetime.now(timezone.utc)
    db.session.add_all([
        ReviewProgress(user_id=1, card_id="hub-00:q", next_review=now + timedelta(days=30)),
        ReviewProgress(user_id=1, card_id="hub-01:q", next_review=now - timedelta(days=1), is_suspended=True),
    ])
    db.session.commit()
