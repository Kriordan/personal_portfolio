import tempfile
import unittest
from pathlib import Path

from project.services.learning_service import ValidationError, create_incident_card


class CreateIncidentCardTests(unittest.TestCase):
    def test_creates_note_for_valid_note_id(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            notes_dir = Path(temporary_directory)

            note_id, card_id = create_incident_card(
                notes_dir=notes_dir,
                note_id="valid-note-1",
                title="Valid note",
                symptom="A symptom",
                root_cause="A cause",
                fix="A fix",
            )

            self.assertEqual(note_id, "valid-note-1")
            self.assertEqual(card_id, "inc")
            self.assertTrue((notes_dir / "valid-note-1.json").is_file())

    def test_rejects_invalid_note_ids(self):
        invalid_note_ids = (
            "../escape",
            "nested/note",
            ".hidden",
            "UPPERCASE",
            "trailing-",
            "a" * 101,
        )

        with tempfile.TemporaryDirectory() as temporary_directory:
            notes_dir = Path(temporary_directory)

            for note_id in invalid_note_ids:
                with self.subTest(note_id=note_id):
                    with self.assertRaisesRegex(ValidationError, "invalid note_id"):
                        create_incident_card(
                            notes_dir=notes_dir,
                            note_id=note_id,
                            title="Invalid note",
                            symptom="A symptom",
                            root_cause="A cause",
                            fix="A fix",
                        )

            self.assertEqual(list(notes_dir.iterdir()), [])


if __name__ == "__main__":
    unittest.main()
