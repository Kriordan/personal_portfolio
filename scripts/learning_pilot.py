"""Explicit local pilot lifecycle. Startup never migrates, seeds, or resets data.

The entry point disables dotenv before importing Flask. Only the dedicated pilot
settings are used; portfolio database URLs and unrelated credentials are ignored.
"""
import argparse
from contextlib import nullcontext
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
import getpass
import os
from pathlib import Path
import secrets
import signal
import sys
from uuid import uuid4

from alembic.config import Config
from alembic.script import ScriptDirectory
from email_validator import validate_email, EmailNotValidError
from flask import abort, jsonify, redirect, request
from flask_migrate import upgrade
from sqlalchemy import select, text
from sqlalchemy.engine import URL
from psycopg.errors import InvalidCatalogName
from werkzeug.serving import make_server

from project import create_app
from project.database import db
from project.extensions import talisman
from project.models import User
from project.learning.content_schema import load_catalog
from project.services import curriculum_service, practice_budget, practice_worker
from scripts import learning_pilot_storage as storage

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_STATE = ROOT / ".local/learning-pilot"
SETTINGS = "settings.json"
APPROVAL = "approval.json"
DRAFT_CATALOG = ROOT / "curriculum/idempotency/catalog-v3.json"


def default_url():
    return URL.create("postgresql+psycopg", username=getpass.getuser(), host="127.0.0.1", port=5432,
                      database=storage.DATABASE).render_as_string(hide_password=False)


def new_settings(database_url, email, port):
    storage.local_url(database_url)
    try:
        email = validate_email(email, check_deliverability=False).normalized
    except EmailNotValidError:
        raise storage.PilotError("Use a valid email-shaped local login name; no email will be sent.") from None
    if type(port) is not int or not 1024 <= port <= 65535:
        raise storage.PilotError("Choose a local web port from 1024 to 65535.")
    return dict(format_version=1, instance_id=str(uuid4()), database_url=database_url, owner_email=email,
        port=port, secret_key=secrets.token_urlsafe(48), jwt_secret_key=secrets.token_urlsafe(48),
        created_at=datetime.now(timezone.utc).isoformat(), restored=False)


def load_settings(directory):
    if not Path(directory).is_dir():
        raise storage.PilotError("Pilot settings do not exist. Run init once before starting or inspecting the pilot.")
    directory = storage.private_directory(directory)
    value = storage.read_json(directory / SETTINGS)
    required = {"format_version", "instance_id", "database_url", "owner_email", "port", "secret_key",
                "jwt_secret_key", "created_at", "restored"}
    if not isinstance(value, dict) or set(value) != required or value["format_version"] != 1:
        raise storage.PilotError("Unrecognized pilot settings format.")
    storage.local_url(value["database_url"])
    storage.database_marker(value["instance_id"])
    if (type(value["port"]) is not int or not 1024 <= value["port"] <= 65535
            or type(value["restored"]) is not bool
            or any(not isinstance(value[key], str) or len(value[key]) < 32 for key in ("secret_key", "jwt_secret_key"))):
        raise storage.PilotError("Invalid pilot settings. Keep the original private settings file.")
    return value


def load_approval(directory, settings):
    path = Path(directory) / APPROVAL
    if not path.exists():
        return None
    value = storage.read_json(path)
    required = {"format_version", "instance_id", "approved_at", "total_microusd", "verification_microusd", "draft_revisions"}
    if (not isinstance(value, dict) or set(value) != required or value["format_version"] != 1
            or value["instance_id"] != settings["instance_id"]
            or type(value["total_microusd"]) is not int or not 0 <= value["total_microusd"] <= 50_000_000
            or type(value["verification_microusd"]) is not int or not 0 <= value["verification_microusd"] <= value["total_microusd"]
            or not isinstance(value["draft_revisions"], list)):
        raise storage.PilotError("Invalid pilot approval. Keep the original approval file and agreed spending limits.")
    for revision in value["draft_revisions"]:
        if (not isinstance(revision, list) or len(revision) != 3 or not isinstance(revision[0], str)
                or type(revision[1]) is not int or revision[1] < 1
                or not isinstance(revision[2], str) or len(revision[2]) != 64
                or any(c not in "0123456789abcdef" for c in revision[2])):
            raise storage.PilotError("Invalid approved draft fingerprint.")
    return value


def _microusd(value):
    try:
        amount = Decimal(str(value)) * 1_000_000
        if not amount.is_finite() or amount != amount.to_integral_value() or not 0 <= amount <= 50_000_000:
            raise ValueError
        return int(amount)
    except (InvalidOperation, ValueError):
        raise storage.PilotError("Use an agreed allowance from $0 to $50, with at most six decimal places.") from None


def authorize(directory, *, total_usd, verification_usd, allow_draft=False):
    """Record an explicit operator approval once; never silently increase it later."""
    total, verification = _microusd(total_usd), _microusd(verification_usd)
    if verification > total:
        raise storage.PilotError("Verification must fit inside the total allowance.")
    with storage.operator_lock(directory):
        settings = load_settings(directory)
        if settings["restored"]:
            raise storage.PilotError("Restored spending must be reconciled before a new live approval. Live AI remains disabled.")
        catalog = load_catalog(DRAFT_CATALOG) if allow_draft else None
        revisions = [[item["id"], item["version"], curriculum_service.content_checksum(item, catalog["schema_version"])]
                     for item in catalog["items"]] if catalog else []
        approval = dict(format_version=1, instance_id=settings["instance_id"],
            approved_at=datetime.now(timezone.utc).isoformat(), total_microusd=total,
            verification_microusd=verification, draft_revisions=revisions)
        previous = load_approval(directory, settings)
        if previous:
            if any(previous[key] != approval[key] for key in ("total_microusd", "verification_microusd", "draft_revisions")):
                raise storage.PilotError("An approval already exists. Changing its allowance or content requires a new reviewed decision.")
            return previous
        app = app_for(settings)
        with app.app_context():
            check_schema()
            if catalog:
                curriculum_service.import_catalog(catalog, dry_run=False)  # no publication or human attestation
            db.session.remove()
            db.engine.dispose()
        # A crash before this write leaves the draft inaccessible and AI disabled.
        storage.write_json(Path(directory) / APPROVAL, approval)
        return approval


def app_for(settings, *, approval=None, live=False, verification=False):
    url = storage.verify_database(settings["database_url"], settings["instance_id"])
    if verification and not live:
        raise storage.PilotError("Verification mode requires explicit live startup.")
    if approval and approval["instance_id"] != settings["instance_id"]:
        raise storage.PilotError("This approval belongs to a different pilot.")
    cap = (approval["verification_microusd"] if verification else approval["total_microusd"]) if approval else 0
    if live and (settings["restored"] or not approval or cap <= 0):
        raise storage.PilotError("Live AI requires a positive approved allowance on the original pilot. Restores stay offline until spending is reconciled.")
    cookie_suffix = settings["instance_id"].split("-")[0]
    app = create_app(dict(SECRET_KEY=settings["secret_key"], JWT_SECRET_KEY=settings["jwt_secret_key"],
        SQLALCHEMY_DATABASE_URI=settings["database_url"], SQLALCHEMY_TRACK_MODIFICATIONS=False,
        SQLALCHEMY_ENGINE_OPTIONS={"connect_args": storage.connect_args(url)},
        WTF_CSRF_ENABLED=True, SESSION_COOKIE_SECURE=False, SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax", SESSION_COOKIE_NAME="learning_pilot_" + cookie_suffix,
        REMEMBER_COOKIE_NAME="learning_pilot_remember_" + cookie_suffix,
        REMEMBER_COOKIE_HTTPONLY=True, REMEMBER_COOKIE_SAMESITE="Lax",
        JWT_ACCESS_TOKEN_EXPIRES=timedelta(minutes=15), JWT_REFRESH_TOKEN_EXPIRES=timedelta(days=30),
        TRUSTED_HOSTS=["127.0.0.1", "localhost", "[::1]"], API_CORS_ORIGINS=[],
        SENTRY_ENABLED=False, RATELIMIT_ENABLED=True, LEARNING_LOCAL_PILOT=True,
        LEARNING_LOCAL_DRAFT_REVISIONS=approval["draft_revisions"] if approval else [],
        LEARNING_PRACTICE_ENABLED=True, LEARNING_AI_ENABLED=live,
        LEARNING_AI_PROVIDER="openai", LEARNING_AI_MODEL="gpt-6.1-sol", LEARNING_AI_SELECTOR_MODEL="gpt-6.1-sol",
        LEARNING_AI_REASONING_EFFORT="low", LEARNING_AI_SERVICE_TIER="default",
        LEARNING_AI_FEEDBACK_MODEL="gpt-6.1-sol", LEARNING_AI_FEEDBACK_REASONING_EFFORT="medium",
        LEARNING_AI_FEEDBACK_MAX_OUTPUT_TOKENS=4000,
        LEARNING_AI_MONTHLY_CAP_USD=50, LEARNING_AI_WARN_USD=40, LEARNING_AI_TOTAL_CAP_USD=cap / 1_000_000,
        LEARNING_AI_CONTEXT_BYTES=524288, LEARNING_AI_CALL_SECONDS=60,
        LEARNING_AI_OWNER_EMAIL=settings["owner_email"]))
    # This entry point binds only to loopback. Production keeps its HTTPS policy.
    talisman.force_https = False
    talisman.session_cookie_secure = False

    @app.before_request
    def local_learning_only():
        if request.remote_addr not in {"127.0.0.1", "::1"}:
            abort(403)
        if request.path == "/":
            return redirect("/learning/")
        if (request.path in {"/login", "/logout", "/pilot/health", "/api/v1/auth/login", "/api/v1/auth/logout",
                             "/api/v1/auth/refresh", "/api/v1/auth/me"}
                or request.path.startswith(("/learning/", "/api/v1/learning/", "/static/"))):
            return None
        abort(404)

    @app.after_request
    def private_local_response(response):
        response.headers["Cache-Control"] = "private, no-store"
        if app.config["LEARNING_LOCAL_DRAFT_REVISIONS"]:
            response.headers["X-Learning-Content-Status"] = "local-draft-pilot"
        return response

    @app.get("/pilot/health")
    def health():
        db.session.execute(text("SELECT 1"))
        return jsonify(status="ok", ai_enabled=app.config["LEARNING_AI_ENABLED"])

    return app


def schema_head():
    config = Config()
    config.set_main_option("script_location", str(ROOT / "migrations"))
    return ScriptDirectory.from_config(config).get_current_head()


def check_schema():
    rows = db.session.execute(text("SELECT version_num FROM alembic_version")).scalars().all()
    if rows != [schema_head()]:
        raise storage.PilotError("Pilot schema differs from this checkout. Stop, back up, and run upgrade before serving.")


def initialize(directory, *, database_url, email, port):
    settings = new_settings(database_url, email, port)
    directory = storage.private_directory(directory, new=True)
    # Persist identity first: an interrupted initialization can be repaired without
    # ever adopting an unrelated database or generating replacement secrets.
    storage.write_json(directory / SETTINGS, settings)
    password = secrets.token_urlsafe(24)
    storage.write_private(directory / "login.txt", f"Email: {settings['owner_email']}\nPassword: {password}\n")
    with storage.operator_lock(directory):
        storage.create_database(database_url, settings["instance_id"])
        finish_initialization(directory, settings)
    return settings


def finish_initialization(directory, settings):
    """Complete a new pilot using its retained identity; never reset an existing login."""
    if settings["restored"]:
        raise storage.PilotError("A restored pilot cannot be initialized again.")
    credentials = storage.private_file(Path(directory) / "login.txt").read_text().splitlines()
    if (len(credentials) != 2 or credentials[0] != f"Email: {settings['owner_email']}"
            or not credentials[1].startswith("Password: ") or len(credentials[1][10:]) < 24):
        raise storage.PilotError("Keep the original private login.txt to finish initialization.")
    app = app_for(settings)
    with app.app_context():
        upgrade(directory=str(ROOT / "migrations"))
        user = db.session.scalar(select(User).where(User.email == settings["owner_email"]))
        if user is None:
            if db.session.scalar(select(User.id).limit(1)) is not None:
                raise storage.PilotError("Unexpected accounts in this pilot. No login was changed.")
            user = User(username="Learning pilot", email=settings["owner_email"], email_verified=True)
            user.set_password(credentials[1][10:])
            db.session.add(user)
            db.session.commit()
        db.session.remove()
        db.engine.dispose()


def resume_initialization(directory):
    with storage.operator_lock(directory):
        settings = load_settings(directory)
        try:
            storage.verify_database(settings["database_url"], settings["instance_id"])
        except InvalidCatalogName:
            storage.create_database(settings["database_url"], settings["instance_id"])
        finish_initialization(directory, settings)


def backup(directory, destination):
    with storage.operator_lock(directory):
        settings = load_settings(directory)
        destination = storage.private_directory(destination, new=True)
        checksum = storage.dump_database(settings["database_url"], settings["instance_id"], destination / "database.dump")
        storage.write_json(destination / SETTINGS, settings)
        approval = load_approval(directory, settings)
        if approval:
            storage.write_json(destination / APPROVAL, approval)
        # No API key is stored in settings, login credentials or database backups.
        storage.write_private(destination / "login.txt", storage.private_file(Path(directory) / "login.txt").read_text())
        storage.write_json(destination / "manifest.json", dict(format_version=1, sha256=checksum,
            created_at=datetime.now(timezone.utc).isoformat(), source_instance=settings["instance_id"]))
        return destination


def restore(backup_directory, destination, database_url):
    original = load_settings(backup_directory)
    manifest = storage.read_json(Path(backup_directory) / "manifest.json")
    if (not isinstance(manifest, dict) or manifest.get("format_version") != 1 or manifest.get("source_instance") != original["instance_id"]
            or not isinstance(manifest.get("sha256"), str)):
        raise storage.PilotError("Unrecognized backup manifest.")
    url = storage.local_url(database_url)
    if not url.database.startswith(("learning_pilot_restored_", "learning_pilot_test_")):
        raise storage.PilotError("Restore into a new learning_pilot_restored_<name> database; never replace the active pilot.")
    destination = storage.private_directory(destination, new=True)
    settings = {**original, "instance_id": str(uuid4()), "database_url": database_url, "restored": True,
                "secret_key": secrets.token_urlsafe(48), "jwt_secret_key": secrets.token_urlsafe(48)}
    storage.write_json(destination / SETTINGS, settings)
    with storage.operator_lock(destination):
        storage.restore_database(database_url, settings["instance_id"], Path(backup_directory) / "database.dump", manifest["sha256"])
        storage.write_private(destination / "login.txt", storage.private_file(Path(backup_directory) / "login.txt").read_text())
        approval = load_approval(backup_directory, original)
        if approval:
            storage.write_json(destination / APPROVAL, {**approval, "instance_id": settings["instance_id"]})
    return settings


def learning_key():
    """Read only Learning's dedicated key; never load portfolio configuration or fall back to another key."""
    from dotenv import dotenv_values
    key = os.environ.get("LEARNING_OPENAI_API_KEY") or dotenv_values(ROOT / ".env", interpolate=False).get("LEARNING_OPENAI_API_KEY")
    if not isinstance(key, str) or not key.strip():
        raise storage.PilotError("Set Learning's dedicated LEARNING_OPENAI_API_KEY before live startup.")
    return key.strip()


def serve(directory, *, live=False, verification=False):
    with storage.operator_lock(directory):
        settings = load_settings(directory)
        approval = load_approval(directory, settings)
        app = app_for(settings, approval=approval, live=live, verification=verification)
        with app.app_context():
            check_schema()
            if db.session.scalar(select(User).where(User.email == settings["owner_email"])) is None:
                raise storage.PilotError("Pilot login is missing; initialization did not finish.")
        signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))
        # Bind successfully before starting a worker: a port collision must not trigger paid work.
        server, worker_started = None, False
        try:
            server = make_server("127.0.0.1", settings["port"], app, threaded=True)
            if live:
                os.environ["LEARNING_OPENAI_API_KEY"] = learning_key()
                practice_worker.start(app)
                worker_started = True
            mode = "live AI (verification allowance)" if verification else "live AI" if live else "AI disabled"
            print(f"Personal pilot: http://127.0.0.1:{settings['port']}/learning/ · persistent data · {mode}", flush=True)
            server.serve_forever()
        finally:
            if worker_started:
                practice_worker.stop(timeout=10)
            if server is not None:
                server.server_close()
            with app.app_context():
                db.session.remove()
                db.engine.dispose()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state-dir", type=Path, default=DEFAULT_STATE)
    commands = parser.add_subparsers(dest="command", required=True)
    init = commands.add_parser("init", help="Create a new isolated database and private login; never reuse an existing database.")
    init.add_argument("--database-url", default=default_url())
    init.add_argument("--email", default="learner@example.com")
    init.add_argument("--port", type=int, default=5068)
    run = commands.add_parser("serve", help="Start on loopback; paid AI requires --live and a recorded allowance.")
    run.add_argument("--live", action="store_true")
    run.add_argument("--verification", action="store_true", help="Use the smaller verification allowance (part of the total).")
    consent = commands.add_parser("authorize", help="Record an explicitly agreed spending/content policy once; never raises an existing allowance.")
    consent.add_argument("--total-usd", required=True)
    consent.add_argument("--verification-usd", required=True)
    consent.add_argument("--allow-idempotency-draft", action="store_true")
    commands.add_parser("resume-init", help="Finish interrupted setup using its original settings and login; never reset existing data.")
    commands.add_parser("status", help="Check identity, schema and login without changing data.")
    save = commands.add_parser("backup", help="Stop the pilot first; save a new private backup directory.")
    save.add_argument("destination", type=Path)
    recover = commands.add_parser("restore", help="Restore into a new database and state directory, with paid AI disabled.")
    recover.add_argument("backup", type=Path)
    recover.add_argument("--database-url", required=True)
    commands.add_parser("upgrade", help="After a backup, explicitly apply pending migrations; startup never migrates.")
    args = parser.parse_args()
    try:
        if args.command == "init":
            initialize(args.state_dir, database_url=args.database_url, email=args.email, port=args.port)
            print(f"Pilot initialized. Local login: {args.state_dir / 'login.txt'}")
        elif args.command == "serve":
            serve(args.state_dir, live=args.live, verification=args.verification)
        elif args.command == "authorize":
            authorize(args.state_dir, total_usd=args.total_usd, verification_usd=args.verification_usd,
                      allow_draft=args.allow_idempotency_draft)
            print("Agreed allowance and exact draft fingerprints recorded. AI still requires serve --live.")
        elif args.command == "resume-init":
            resume_initialization(args.state_dir)
            print("Pilot initialization completed using the original identity and login.")
        elif args.command == "backup":
            print("Backup saved:", backup(args.state_dir, args.destination))
        elif args.command == "restore":
            restore(args.backup, args.state_dir, args.database_url)
            print("Restored to a new private database. Paid AI remains disabled; reconcile spending before authorizing it.")
        else:
            with storage.operator_lock(args.state_dir) if args.command == "upgrade" else nullcontext():
                settings = load_settings(args.state_dir)
                approval = load_approval(args.state_dir, settings)
                app = app_for(settings, approval=approval)
                with app.app_context():
                    if args.command == "upgrade":
                        upgrade(directory=str(ROOT / "migrations"))
                    check_schema()
                    if db.session.scalar(select(User.id).where(User.email == settings["owner_email"])) is None:
                        raise storage.PilotError("Pilot login is missing; use resume-init to finish interrupted setup.")
                    print("Pilot database identity, schema and login verified.")
                    print(f"Committed AI spend: ${practice_budget.committed() / 1_000_000:.6f}; "
                          f"approved total: ${(approval['total_microusd'] if approval else 0) / 1_000_000:.2f}. "
                          "This command makes no paid calls.")
                    if settings["restored"]:
                        print("Restored pilot: live AI is blocked pending spending reconciliation and new approval.")
    except (storage.PilotError, FileExistsError) as exc:
        parser.exit(1, (str(exc) if isinstance(exc, storage.PilotError) else "Destination already exists; nothing was overwritten.") + "\n")
    except Exception as exc:
        # A database exception can contain connection details. Print only its type.
        parser.exit(1, f"Pilot operation failed ({type(exc).__name__}). Existing data was retained; inspect local configuration and server availability.\n")


if __name__ == "__main__":
    main()
