import os

from project import create_app
from project.services import practice_worker


def main():
    app = create_app()
    # The Learning reply worker runs here only: never in create_app, CLI commands, or tests.
    if practice_worker.should_start(app):
        practice_worker.start(app)
    port = int(os.environ.get("PORT", 5001))
    app.run(host="0.0.0.0", port=port)


if __name__ == "__main__":
    main()
