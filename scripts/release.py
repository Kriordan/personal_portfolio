"""Heroku release phase: no provider work; any failure prevents the new release."""
import os
from pathlib import Path
import sys

os.environ["PYTHON_DOTENV_DISABLED"] = "1"
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def main():
    from project import create_app
    from project.deployment import release
    from project.database import db
    try:
        app = create_app()
        with app.app_context():
            try:
                release()
                print("Release schema and Learning configuration verified; no AI calls were made.")
            finally:
                db.session.remove()
                db.engine.dispose()
    except Exception as exc:
        # A configuration or DB exception may contain sensitive connection details.
        print(f"Release preparation failed ({type(exc).__name__}). The new release must not serve traffic.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
