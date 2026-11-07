"""Local-only pilot storage. No application configuration, keys or paid calls.

Database creation is exclusive; existing databases are never adopted or replaced.
An instance UUID in the database comment binds it to its private settings file.
"""
from contextlib import contextmanager
import fcntl
import getpass
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
from uuid import UUID

import psycopg
from psycopg import sql
from sqlalchemy.engine import make_url
from sqlalchemy.exc import ArgumentError

DATABASE = "learning_personal_pilot"
MARKER = "learning-pilot-v1:"


class PilotError(ValueError):
    """Safe operator-facing errors: never include connection strings or secrets."""


def local_url(value):
    try:
        url = make_url(value)
        valid = (url.drivername == "postgresql+psycopg" and url.host in {"127.0.0.1", "localhost", "::1"}
                 and not url.query and (url.port is None or 1 <= url.port <= 65535)
                 and (url.database == DATABASE or re.fullmatch(r"learning_pilot_(?:test|restored)_[a-z0-9]{1,20}", url.database or "")))
    except (ValueError, TypeError, ArgumentError):
        valid = False
    if not valid:
        raise PilotError("Use a loopback PostgreSQL URL with the dedicated pilot database name; remote databases and URL options are refused.")
    return url


def connect_args(url, *, admin=False):
    values = dict(host=url.host, port=url.port or 5432, dbname="postgres" if admin else url.database,
                  hostaddr="::1" if url.host == "::1" else "127.0.0.1",
                  user=url.username or getpass.getuser(), password=url.password or "", options="", passfile="",
                  connect_timeout=5, application_name="learning-personal-pilot")
    return values


def database_marker(instance_id):
    try:
        valid = isinstance(instance_id, str) and str(UUID(instance_id)) == instance_id
    except ValueError:
        valid = False
    if not valid:
        raise PilotError("Invalid pilot instance identity.")
    return MARKER + instance_id


def create_database(value, instance_id):
    url = local_url(value)
    marker = database_marker(instance_id)
    with psycopg.connect(**connect_args(url, admin=True), autocommit=True) as connection:
        if connection.execute("SELECT 1 FROM pg_database WHERE datname = %s", (url.database,)).fetchone():
            raise PilotError("The target database already exists. Nothing was changed; use its original settings or a new restore destination.")
        # CREATE DATABASE also atomically rejects a racing creator.
        connection.execute(sql.SQL("CREATE DATABASE {} TEMPLATE template0 ENCODING 'UTF8'").format(sql.Identifier(url.database)))
        connection.execute(sql.SQL("COMMENT ON DATABASE {} IS {}").format(sql.Identifier(url.database), sql.Literal(marker)))
    return url


def verify_database(value, instance_id):
    url = local_url(value)
    with psycopg.connect(**connect_args(url)) as connection:
        row = connection.execute("SELECT shobj_description(oid, 'pg_database') FROM pg_database WHERE datname = current_database()").fetchone()
    if not row or row[0] != database_marker(instance_id):
        raise PilotError("This database does not belong to these pilot settings. No changes were made.")
    return url


def private_directory(path, *, new=False):
    path = Path(path).absolute()
    if path.is_symlink():
        raise PilotError("Pilot storage must be a private directory, not a symbolic link.")
    path.mkdir(mode=0o700, parents=True, exist_ok=not new)
    metadata = path.stat()
    if not stat.S_ISDIR(metadata.st_mode) or metadata.st_mode & 0o077 or metadata.st_uid != os.getuid():
        raise PilotError("Pilot storage must be owned by you with permissions 700.")
    return path


def private_file(path):
    metadata = Path(path).lstat()
    if not stat.S_ISREG(metadata.st_mode) or metadata.st_mode & 0o077 or metadata.st_uid != os.getuid():
        raise PilotError("Pilot settings and backups must be private regular files (permissions 600).")
    return Path(path)


def write_private(path, data):
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w") as handle:
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())


def write_json(path, data):
    write_private(path, json.dumps(data, indent=2, sort_keys=True) + "\n")


def read_json(path):
    return json.loads(private_file(path).read_text())


@contextmanager
def operator_lock(directory):
    """One server/operator per settings directory; never wait behind a running app."""
    if not Path(directory).is_dir():
        raise PilotError("Pilot settings do not exist. Run init once before starting or inspecting the pilot.")
    directory = private_directory(directory)
    descriptor = os.open(directory / "operator.lock", os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    try:
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise PilotError("The pilot is already running or another operation is active. Stop it before backing up or upgrading.") from None
        yield
    finally:
        os.close(descriptor)


def postgres_binary(name):
    if name not in {"pg_dump", "pg_restore"}:
        raise PilotError("Unsupported PostgreSQL utility.")
    binary = shutil.which(name)
    if binary:
        return binary
    bundled = Path("/Applications/Postgres.app/Contents/Versions/18/bin") / name
    if bundled.is_file():
        return str(bundled)
    raise PilotError("Install PostgreSQL client tools and put pg_dump and pg_restore on PATH.")


def _postgres_command(name, url):
    args = [postgres_binary(name), "--host", "127.0.0.1" if url.host == "localhost" else url.host,
            "--port", str(url.port or 5432), "--no-password"]
    if url.username:
        args += ["--username", url.username]
    # Do not inherit PGHOST, PGSERVICE, PGOPTIONS or arbitrary connection settings.
    env = {"PATH": os.environ.get("PATH", ""), "PGCONNECT_TIMEOUT": "5", "PGAPPNAME": "learning-personal-pilot"}
    if url.password:
        env["PGPASSWORD"] = url.password
    return args, env


def dump_database(value, instance_id, path):
    url = verify_database(value, instance_id)
    args, env = _postgres_command("pg_dump", url)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            result = subprocess.run(args + ["--format=custom", "--no-owner", "--no-privileges", url.database],
                env=env, stdout=handle, stderr=subprocess.PIPE, timeout=120)
        if result.returncode:
            raise PilotError("PostgreSQL backup failed. Check that the local server and matching client tools are available.")
    except Exception:
        Path(path).unlink(missing_ok=True)  # Only the new incomplete file created above.
        raise
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def restore_database(value, instance_id, path, checksum):
    # Validate input before creating a database. Restore always uses a fresh name.
    path = private_file(path)
    if hashlib.sha256(path.read_bytes()).hexdigest() != checksum:
        raise PilotError("Backup checksum mismatch. Nothing was restored.")
    url = create_database(value, instance_id)
    args, env = _postgres_command("pg_restore", url)
    result = subprocess.run(args + ["--single-transaction", "--exit-on-error", "--no-owner", "--no-privileges",
                                   "--dbname", url.database, str(path)],
        env=env, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, timeout=120)
    if result.returncode:
        raise PilotError("Restore failed; its new database was retained for inspection. Existing databases were not changed.")
    return url
