"""One threaded web process, preserving Socket.IO rooms and the Learning worker.

Heroku terminates TLS at its router. Only there do we accept its forwarded HTTPS
header from arbitrary router IPs; local execution trusts loopback only.
"""
import os

bind = "0.0.0.0:" + os.environ.get("PORT", "5001")
workers = 1
worker_class = "gthread"
threads = 8
preload_app = False
reload = False
timeout = 30
graceful_timeout = 20
control_socket_disable = True
accesslog = None  # No cookies, tokens, or learner text in application access logs.
errorlog = "-"
forwarded_allow_ips = "*" if os.environ.get("DYNO") else "127.0.0.1,::1"
secure_scheme_headers = {"X-FORWARDED-PROTO": "https"}
forwarder_headers = ""


def on_starting(server):
    if (server.cfg.workers != 1 or server.cfg.preload_app or server.cfg.reload
            or server.cfg.worker_class.__module__ != "gunicorn.workers.gthread" or server.cfg.threads < 2):
        raise RuntimeError("Use one threaded web process without preload or reload for this pilot.")


def post_worker_init(worker):
    from project.deployment import check_ready
    from project.services import practice_worker
    app = worker.wsgi
    with app.app_context():
        check_ready()
    if practice_worker.should_start(app):
        practice_worker.start(app)
        worker.learning_worker_started = True


def worker_exit(server, worker):
    from project.services import practice_worker
    if getattr(worker, "learning_worker_started", False):
        practice_worker.stop(timeout=5)
