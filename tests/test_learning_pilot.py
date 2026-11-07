"""Operator policy and key isolation; no database, network, or paid calls."""
import copy
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from uuid import uuid4

from scripts import learning_pilot as pilot, learning_pilot_storage as storage


class PilotPolicyTests(unittest.TestCase):
    def test_allowances_are_finite_precise_and_within_the_existing_monthly_cap(self):
        self.assertEqual(pilot._microusd("5"), 5_000_000)
        self.assertEqual(pilot._microusd("0.000001"), 1)
        for value in ("NaN", "Infinity", "-1", "50.000001", "0.0000001", "not-money"):
            with self.subTest(value=value), self.assertRaises(storage.PilotError):
                pilot._microusd(value)

    def test_malformed_or_foreign_approvals_fail_closed(self):
        settings = pilot.new_settings("postgresql+psycopg://owner@127.0.0.1/learning_personal_pilot", "learner@example.com", 5068)
        valid = dict(format_version=1, instance_id=settings["instance_id"], approved_at="2026-11-07T00:00:00Z",
                     total_microusd=5_000_000, verification_microusd=1_000_000,
                     draft_revisions=[["idempotency", 2, "a" * 64]])
        mutations = [lambda p: p.update(instance_id=str(uuid4())), lambda p: p.update(total_microusd=True),
                     lambda p: p.update(verification_microusd=6_000_000), lambda p: p.update(total_microusd=-1),
                     lambda p: p.update(extra="unknown"), lambda p: p["draft_revisions"][0].__setitem__(2, "z" * 64)]
        with tempfile.TemporaryDirectory() as root:
            for index, mutation in enumerate([None, *mutations]):
                directory = storage.private_directory(Path(root) / str(index), new=True)
                candidate = copy.deepcopy(valid)
                if mutation:
                    mutation(candidate)
                storage.write_json(directory / pilot.APPROVAL, candidate)
                if mutation:
                    with self.assertRaises(storage.PilotError):
                        pilot.load_approval(directory, settings)
                else:
                    self.assertEqual(pilot.load_approval(directory, settings), valid)

    def test_only_the_learning_key_is_read_and_no_dotenv_values_are_exported(self):
        with patch.dict(os.environ, {"OPENAI_API_KEY": "unrelated-key"}, clear=True):
            with patch("dotenv.dotenv_values", return_value={"OPENAI_API_KEY": "another-unrelated-key"}):
                with self.assertRaises(storage.PilotError):
                    pilot.learning_key()
            with patch("dotenv.dotenv_values", return_value={"LEARNING_OPENAI_API_KEY": "fixture-key", "DATABASE_URL": "unrelated"}) as read:
                self.assertEqual(pilot.learning_key(), "fixture-key")
                read.assert_called_once_with(pilot.ROOT / ".env", interpolate=False)
                self.assertNotIn("DATABASE_URL", os.environ)
                self.assertNotIn("LEARNING_OPENAI_API_KEY", os.environ)
            with patch.dict(os.environ, LEARNING_OPENAI_API_KEY="explicit-learning-key"):
                with patch("dotenv.dotenv_values") as read:
                    self.assertEqual(pilot.learning_key(), "explicit-learning-key")
                    read.assert_not_called()
