import unittest
from types import SimpleNamespace

from project.learning.queue_builder import build_review_queue


class QueueBuilderTests(unittest.TestCase):
    def test_build_review_queue_interleaves_and_keeps_all_cards(self):
        due_cards = [
            {"card_id": "note-a:1", "note_id": "note-a", "tags": ["db"]},
            {"card_id": "note-a:2", "note_id": "note-a", "tags": ["db"]},
            {"card_id": "note-a:3", "note_id": "note-a", "tags": ["db"]},
            {"card_id": "note-b:1", "note_id": "note-b", "tags": ["api"]},
            {"card_id": "note-b:2", "note_id": "note-b", "tags": ["api"]},
            {"card_id": "note-c:1", "note_id": "note-c", "tags": ["infra"]},
        ]
        progress_map = {
            "note-a:1": SimpleNamespace(lapses=2, interval=1, learning_state="review", last_rating=4),
            "note-a:2": SimpleNamespace(lapses=1, interval=2, learning_state="review", last_rating=4),
            "note-a:3": SimpleNamespace(lapses=0, interval=3, learning_state="review", last_rating=4),
            "note-b:1": SimpleNamespace(lapses=0, interval=1, learning_state="learning", last_rating=2),
            "note-b:2": SimpleNamespace(lapses=0, interval=2, learning_state="review", last_rating=4),
            "note-c:1": SimpleNamespace(lapses=0, interval=1, learning_state="relearning", last_rating=1),
        }

        queue = build_review_queue(due_cards, progress_map, seed=42)

        self.assertEqual({card["card_id"] for card in queue}, {card["card_id"] for card in due_cards})

        for idx in range(2, len(queue)):
            note_id = queue[idx]["note_id"]
            self.assertFalse(
                queue[idx - 1]["note_id"] == note_id and queue[idx - 2]["note_id"] == note_id
            )

        for idx in range(3, len(queue)):
            tag = (queue[idx].get("tags") or [None])[0]
            recent_tags = [
                (queue[idx - 1].get("tags") or [None])[0],
                (queue[idx - 2].get("tags") or [None])[0],
                (queue[idx - 3].get("tags") or [None])[0],
            ]
            if tag is not None:
                self.assertFalse(all(recent_tag == tag for recent_tag in recent_tags))

    def test_build_review_queue_is_deterministic_with_seed(self):
        due_cards = [
            {"card_id": "note-a:1", "note_id": "note-a", "tags": ["db"]},
            {"card_id": "note-b:1", "note_id": "note-b", "tags": ["api"]},
            {"card_id": "note-c:1", "note_id": "note-c", "tags": ["infra"]},
        ]
        progress_map = {
            "note-a:1": SimpleNamespace(lapses=1, interval=2, learning_state="review", last_rating=4),
            "note-b:1": SimpleNamespace(lapses=0, interval=1, learning_state="review", last_rating=4),
            "note-c:1": SimpleNamespace(lapses=0, interval=3, learning_state="review", last_rating=4),
        }

        first = build_review_queue(due_cards, progress_map, seed=7)
        second = build_review_queue(due_cards, progress_map, seed=7)

        self.assertEqual([card["card_id"] for card in first], [card["card_id"] for card in second])
