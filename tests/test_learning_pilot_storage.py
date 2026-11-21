"""Loopback and private-file boundaries without a database or paid provider."""
import os
from pathlib import Path
import tempfile
import unittest
from uuid import uuid4

from scripts import learning_pilot_storage as storage


class PilotStorageTests(unittest.TestCase):
    def test_only_named_local_postgres_databases_are_accepted(self):
        for host in ("127.0.0.1", "localhost", "[::1]"):
            url = storage.local_url(f"postgresql+psycopg://user:private@{host}:5432/learning_personal_pilot")
            self.assertEqual(url.database, storage.DATABASE)
        for value in ("sqlite:///pilot.db", "postgresql://localhost/learning_personal_pilot",
                      "postgresql+psycopg://remote.example.com/learning_personal_pilot",
                      "postgresql+psycopg://localhost/portfolio", "postgresql+psycopg:///learning_personal_pilot",
                      "postgresql+psycopg://localhost/learning_personal_pilot?host=remote.example.com",
                      "postgresql+psycopg://localhost/learning_personal_pilot?options=-csearch_path=other",
                      "postgresql+psycopg://localhost:0/learning_personal_pilot", "bad", None):
            with self.subTest(value=value), self.assertRaises(storage.PilotError) as raised:
                storage.local_url(value)
            self.assertNotIn("private", str(raised.exception))

    def test_private_files_are_exclusive_and_symlinks_are_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            root = storage.private_directory(Path(folder) / "pilot", new=True)
            self.assertEqual(root.stat().st_mode & 0o777, 0o700)
            path = root / "settings.json"
            storage.write_json(path, {"instance_id": str(uuid4())})
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            original = storage.read_json(path)
            with self.assertRaises(FileExistsError):
                storage.write_json(path, {})
            self.assertEqual(storage.read_json(path), original)
            link = root / "linked.json"
            link.symlink_to(path)
            with self.assertRaises(storage.PilotError):
                storage.read_json(link)
            path.chmod(0o644)
            with self.assertRaises(storage.PilotError):
                storage.read_json(path)
            root.chmod(0o755)
            with self.assertRaises(storage.PilotError):
                storage.private_directory(root)

    def test_operator_lock_excludes_overlapping_processes_and_releases_on_failure(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder) / "pilot"
            with self.assertRaises(storage.PilotError):
                with storage.operator_lock(root):
                    self.fail("Missing settings must not create a new directory")
            self.assertFalse(root.exists())
            storage.private_directory(root, new=True)
            with self.assertRaises(RuntimeError):
                with storage.operator_lock(root):
                    with self.assertRaises(storage.PilotError):
                        with storage.operator_lock(root):
                            self.fail("A second operator acquired the lock")
                    raise RuntimeError("fixture")
            with storage.operator_lock(root):
                pass

    def test_postgres_child_environment_cannot_redirect_the_database(self):
        from unittest.mock import patch
        url = storage.local_url("postgresql+psycopg://owner:secret@127.0.0.1/learning_personal_pilot")
        with patch.dict(os.environ, PGHOST="remote", PGSERVICE="prod", PGOPTIONS="secret-options", OPENAI_API_KEY="other"):
            with patch.object(storage, "postgres_binary", return_value="pg_dump"):
                command, env = storage._postgres_command("pg_dump", url)
        self.assertNotIn("secret", str(command))
        self.assertEqual(env["PGPASSWORD"], "secret")
        self.assertTrue(set(env) <= {"PATH", "PGPASSWORD", "PGCONNECT_TIMEOUT", "PGAPPNAME"})
        options = storage.connect_args(url)
        self.assertEqual(options["hostaddr"], "127.0.0.1")  # PGHOSTADDR cannot redirect a loopback URL
        self.assertEqual(options["options"], "")
        self.assertEqual(options["passfile"], "")
        self.assertEqual(options["user"], "owner")
        with patch.object(storage, "postgres_binary", return_value="pg_dump"):
            command, _ = storage._postgres_command("pg_dump", url.set(host="localhost"))
            self.assertEqual(command[command.index("--host") + 1], "127.0.0.1")
