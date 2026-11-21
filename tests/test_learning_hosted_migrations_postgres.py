"""Rehearse the hosted rollout from the actual production schema on isolated PostgreSQL."""
from datetime import datetime, timedelta, timezone
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch
from uuid import uuid4

from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from flask_migrate import upgrade
import psycopg
from psycopg import sql
from sqlalchemy import MetaData, Table, select, text
from sqlalchemy.engine import make_url

from project import create_app
from project.database import db
from project.models import CustomList, ListCategory, ListItem, ReviewProgress, ReviewReceipt, User
from scripts import learning_pilot_storage as storage

URL = os.environ.get("LIBRARY_TEST_POSTGRES_URL")
ROOT = Path(__file__).resolve().parents[1]
DEPLOYED_REVISION = "a4b5c6d7e8f9"  # Heroku v164, inspected November 13, 2026.


@unittest.skipUnless(URL, "Set LIBRARY_TEST_POSTGRES_URL to the isolated local test database")
class HostedPostgresCase(unittest.TestCase):
    def setUp(self):
        self.source = make_url(URL)
        if self.source.host not in {"127.0.0.1", "localhost"} or self.source.database != "library_sync_test":
            raise RuntimeError("Refusing fixtures outside the isolated local test server")
        self.databases = []

    def target(self):
        url = self.source.set(database="learning_pilot_test_" + uuid4().hex[:12])
        identity = str(uuid4())
        self.databases.append((url, identity))
        return url.render_as_string(hide_password=False), identity

    def app(self, url):
        return create_app(dict(TESTING=True, SECRET_KEY="fixture", SQLALCHEMY_DATABASE_URI=url,
                               SENTRY_ENABLED=False, LEARNING_AI_ENABLED=False))

    def tearDown(self):
        for url, identity in self.databases:
            with psycopg.connect(**storage.connect_args(url, admin=True), autocommit=True) as connection:
                marker = connection.execute(
                    "SELECT shobj_description(oid, 'pg_database') FROM pg_database WHERE datname = %s",
                    (url.database,),
                ).fetchone()
                if marker:
                    self.assertEqual(marker[0], storage.database_marker(identity))
                    connection.execute(sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(url.database)))

class HostedMigrationPostgresTests(HostedPostgresCase):
    @patch("logging.config.fileConfig")
    def test_failed_migration_rolls_back_schema_and_revision(self, _logging):
        url, identity = self.target()
        storage.create_database(url, identity)
        with self.app(url).app_context(), tempfile.TemporaryDirectory() as directory:
            upgrade(directory=str(ROOT / "migrations"), revision=DEPLOYED_REVISION)
            copied = Path(directory) / "migrations"
            shutil.copytree(ROOT / "migrations", copied)
            # Fail after DDL, rather than before connecting, to exercise real
            # PostgreSQL transaction rollback across the entire pending chain.
            (copied / "versions" / "fixture_failure.py").write_text(
                'from alembic import op\nimport sqlalchemy as sa\n'
                'revision = "fixture_failure"\ndown_revision = "e4f5a6b7c8d9"\n'
                'def upgrade():\n'
                '    op.create_table("fixture_partial_table", sa.Column("id", sa.Integer))\n'
                '    raise RuntimeError("deliberate migration failure")\n'
                'def downgrade():\n    pass\n'
            )
            with self.assertRaises(SystemExit) as failure:
                upgrade(directory=str(copied))
            self.assertEqual(failure.exception.code, 1)
            self.assertEqual(db.session.execute(text("SELECT version_num FROM alembic_version")).scalar(),
                             DEPLOYED_REVISION)
            self.assertIsNone(db.session.execute(text("SELECT to_regclass('fixture_partial_table')")).scalar())
            self.assertIsNone(db.session.execute(text("SELECT to_regclass('content_revision')")).scalar())
            db.session.remove()
            upgrade(directory=str(ROOT / "migrations"))
            db.engine.dispose()

    def test_concurrent_release_processes_wait_then_apply_migrations_once(self):
        url, identity = self.target()
        storage.create_database(url, identity)
        code = """
import os
from flask_migrate import upgrade
from project import create_app
from project.database import db
app = create_app(dict(TESTING=True, SECRET_KEY='fixture', SENTRY_ENABLED=False,
    SQLALCHEMY_DATABASE_URI=os.environ['HOSTED_MIGRATION_FIXTURE_URL']))
with app.app_context():
    upgrade(directory='migrations')
    db.engine.dispose()
"""
        env = dict(os.environ, PYTHON_DOTENV_DISABLED="1", AWS_EC2_METADATA_DISABLED="true",
                   HOSTED_MIGRATION_FIXTURE_URL=url)
        children = []
        try:
            with psycopg.connect(**storage.connect_args(make_url(url))) as connection:
                connection.execute("SELECT pg_advisory_xact_lock(1427870284, 3)")
                for _ in range(2):
                    children.append(subprocess.Popen([sys.executable, "-c", code], cwd=ROOT, env=env,
                        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True))
                deadline = time.monotonic() + 15
                waiting = 0
                while waiting != 2 and time.monotonic() < deadline:
                    waiting = connection.execute(
                        "SELECT count(*) FROM pg_stat_activity WHERE datname = current_database() "
                        "AND pid != pg_backend_pid() AND wait_event = 'advisory'"
                    ).fetchone()[0]
                    # pg_stat_activity is cached per transaction without clearing.
                    connection.execute("SELECT pg_stat_clear_snapshot()")
                    if waiting != 2:
                        time.sleep(0.05)
                self.assertEqual(waiting, 2)
                self.assertTrue(all(child.poll() is None for child in children))
            for child in children:
                stdout, stderr = child.communicate(timeout=20)
                self.assertEqual(child.returncode, 0, stdout + stderr)
            with self.app(url).app_context():
                with db.engine.connect() as connection:
                    self.assertEqual(compare_metadata(MigrationContext.configure(connection), db.metadata), [])
                db.engine.dispose()
        finally:
            for child in children:
                if child.poll() is None:
                    child.terminate()
                child.communicate(timeout=10)

    @patch("logging.config.fileConfig")
    def test_upgrade_from_deployed_schema_preserves_data_and_backup_restores(self, _logging):
        url, identity = self.target()
        storage.create_database(url, identity)
        app = self.app(url)
        with app.app_context():
            upgrade(directory=str(ROOT / "migrations"), revision=DEPLOYED_REVISION)
            user = User(id=1, username="migration-fixture", email="fixture@example.test", email_verified=True)
            # Heroku's schema ownership makes pg_dump explicitly recreate public.
            # Restore must handle that on its exclusively created, empty target.
            db.session.execute(text("ALTER SCHEMA public OWNER TO CURRENT_USER"))
            user.set_password("A deterministic migration fixture password")
            db.session.add(user)
            db.session.flush()
            due = datetime(2026, 11, 14, 15, tzinfo=timezone.utc)
            db.session.add(ReviewProgress(user_id=1, card_id="legacy:q", revision=7,
                learning_state="review", scheduler_version="sm2_v2_steps", repetitions=4,
                next_review=due, interval=9, easiness=2.35, last_rating=4, lapses=2))
            db.session.add(ReviewReceipt(user_id=1, request_id=str(uuid4()), payload={"card_id": "legacy:q"},
                response={"next_review": due.isoformat()}, created_at=due - timedelta(days=9)))
            groceries = CustomList(title="Preserved groceries", owner_id=1)
            category = ListCategory(name="Produce", custom_list=groceries)
            db.session.add(ListItem(name="Apples", quantity="3", category=category, completed=True))
            db.session.commit()
            # Use the real deployed table definition: the current ORM includes a
            # content_version column that this migration has not added yet.
            log = Table("review_log", MetaData(), autoload_with=db.engine)
            with db.engine.begin() as connection:
                connection.execute(log.insert().values(user_id=1, card_id="legacy:q", reviewed_at=due,
                    rating=4, scheduler_version="sm2_v2_steps", interval_before=4, interval_after=9,
                    easiness_before=2.35, easiness_after=2.35, repetitions_before=3, repetitions_after=4,
                    next_review_before=due, next_review_after=due + timedelta(days=9)))
            tables = [Table(name, MetaData(), autoload_with=db.engine) for name in
                      ("user", "review_progress", "review_receipt", "review_log", "custom_list", "list_category", "list_item")]
            before = {table.name: [dict(row) for row in db.session.execute(select(table)).mappings()]
                      for table in tables}
            db.session.remove()
            with tempfile.TemporaryDirectory() as directory:
                backup = Path(directory) / "before-upgrade.dump"
                checksum = storage.dump_database(url, identity, backup)
                for _ in range(2):  # A config-only release must also be safe to repeat.
                    upgrade(directory=str(ROOT / "migrations"))
                    for table in tables:
                        self.assertEqual([dict(row) for row in db.session.execute(select(table)).mappings()],
                                         before[table.name])
                    self.assertIsNone(db.session.execute(text("SELECT content_version FROM review_log")).scalar())
                    self.assertEqual(db.session.execute(text("SELECT count(*) FROM content_revision")).scalar(), 0)
                    db.session.remove()
                with db.engine.connect() as connection:
                    self.assertEqual(compare_metadata(MigrationContext.configure(connection), db.metadata), [])
                restored_url, restored_identity = self.target()
                storage.restore_database(restored_url, restored_identity, backup, checksum)
                with self.app(restored_url).app_context():
                    self.assertEqual(db.session.execute(text("SELECT version_num FROM alembic_version")).scalar(),
                                     DEPLOYED_REVISION)
                    for table in tables:
                        self.assertEqual([dict(row) for row in db.session.execute(select(table)).mappings()],
                                         before[table.name])
                    db.session.remove()
                    db.engine.dispose()
            db.engine.dispose()
