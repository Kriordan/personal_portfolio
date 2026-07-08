import unittest

from project.services.learning_service import build_cards


class CardBuilderTests(unittest.TestCase):
    def test_build_cards_supports_types_and_tags(self):
        notes = [
            {
                "id": "note-1",
                "title": "Sample Note",
                "tags": ["postgresql", "sqlalchemy"],
                "flashcards": [
                    {
                        "id": "qa-1",
                        "question": "What is timestamptz?",
                        "answer": "Timezone-aware timestamp.",
                    },
                    {
                        "id": "inc-1",
                        "type": "incident",
                        "symptom": "TypeError comparing naive and aware",
                        "root_cause": "timestamp without timezone",
                        "fix": "use DateTime(timezone=True)",
                        "prevention": "add regression test",
                        "tags": ["datetime"],
                    },
                    {
                        "id": "cloze-1",
                        "type": "cloze",
                        "text": "Use {{c1::timestamptz}} for real points in time.",
                    },
                    {
                        "id": "cmd-1",
                        "type": "command",
                        "prompt": "Convert column to timestamptz",
                        "answer": "ALTER COLUMN ... TYPE timestamptz USING col AT TIME ZONE 'UTC';",
                    },
                    {
                        "id": "diff-1",
                        "type": "code_diff",
                        "prompt": "Fix model timestamps",
                        "before": "db.DateTime()",
                        "after": "db.DateTime(timezone=True)",
                    },
                ],
            }
        ]

        cards = build_cards(notes)
        cards_by_id = {card["card_id"]: card for card in cards}

        qa = cards_by_id["note-1:qa-1"]
        self.assertEqual(qa["type"], "qa")
        self.assertEqual(qa["prompt"], "What is timestamptz?")
        self.assertEqual(qa["response"], "Timezone-aware timestamp.")

        incident = cards_by_id["note-1:inc-1"]
        self.assertEqual(incident["type"], "incident")
        self.assertIn("Symptom:", incident["prompt"])
        self.assertIn("Root cause:", incident["response"])
        self.assertIn("Fix:", incident["response"])
        self.assertIn("Prevention:", incident["response"])
        self.assertIn("datetime", incident["tags"])

        cloze = cards_by_id["note-1:cloze-1"]
        self.assertEqual(cloze["type"], "cloze")
        self.assertIn("[...]", cloze["prompt"])
        self.assertIn("timestamptz", cloze["response"])

        command = cards_by_id["note-1:cmd-1"]
        self.assertEqual(command["type"], "command")
        self.assertEqual(command["prompt"], "Convert column to timestamptz")
        self.assertIn("ALTER COLUMN", command["response"])

        diff = cards_by_id["note-1:diff-1"]
        self.assertEqual(diff["type"], "code_diff")
        self.assertIn("Before:", diff["response"])
        self.assertIn("After:", diff["response"])

        merged_tags = cards_by_id["note-1:inc-1"]["tags"]
        self.assertEqual(merged_tags, ["postgresql", "sqlalchemy", "datetime"])
