"""Real threaded production server, TLS-router headers, WebSockets and restart recovery."""
from contextlib import contextmanager
import json
import os
import re
import socket
import subprocess
import sys
import tempfile
import time
from unittest.mock import patch
from uuid import uuid4

from flask_migrate import upgrade
import requests
import websocket

from project import create_app
from project.database import db
from project.deployment import release
from project.models import CustomList, User
from scripts import learning_pilot_storage as storage
from tests.hosted_pilot_fixtures import approval, config, environment
from tests.test_learning_hosted_migrations_postgres import DEPLOYED_REVISION, HostedPostgresCase, ROOT

PASSWORD = "Deterministic hosted fixture password"
HEADERS = {"Host": "www.keithriordan.com", "X-Forwarded-Proto": "https"}
API = "/api/v1/learning/practice/sessions"


class HostedServerTests(HostedPostgresCase):
    def seed(self, *, ready=True):
        url, identity = self.target()
        storage.create_database(url, identity)
        app = create_app(config(url))
        with app.app_context():
            upgrade(directory=str(ROOT / "migrations"), revision=DEPLOYED_REVISION)
            for number, email in ((1, "owner@example.com"), (2, "other@example.com")):
                user = User(id=number, username=f"fixture-{number}", email=email, email_verified=True)
                user.set_password(PASSWORD)
                db.session.add(user)
            db.session.commit()
            db.session.add(CustomList(id=1, title="Existing grocery list", owner_id=1))
            db.session.commit()
            if ready:
                release()
            db.session.remove()
            db.engine.dispose()
        return url

    @contextmanager
    def server(self, url, *, live=False, options=(), must_boot=True):
        with socket.socket() as listener:
            listener.bind(("127.0.0.1", 0))
            port = listener.getsockname()[1]
        env = {key: value for key, value in os.environ.items() if key in {"PATH", "SYSTEMROOT", "TMPDIR", "LANG"}}
        env.update(environment(mode="verification" if live else "off"), DATABASE_URL=url,
            SECRET_KEY="fixture-secret-at-least-32-characters", PYTHON_DOTENV_DISABLED="1",
            AWS_EC2_METADATA_DISABLED="true", SENTRY_ENABLED="0", PORT=str(port),
            LEARNING_OPENAI_API_KEY="fixture-never-used", HOSTED_FIXTURE_FAKE_AI="1" if live else "0")
        with tempfile.TemporaryFile(mode="w+") as output:
            child = subprocess.Popen([sys.executable, "-m", "gunicorn", "--config", "gunicorn.conf.py",
                "tests.hosted_server_fixture:app()", *options], cwd=ROOT, env=env, stdout=output, stderr=output)
            base = f"http://127.0.0.1:{port}"
            try:
                if must_boot:
                    deadline = time.monotonic() + 20
                    while time.monotonic() < deadline and child.poll() is None:
                        try:
                            if requests.get(base + "/", headers=HEADERS, timeout=0.5).status_code == 200:
                                break
                        except requests.RequestException:
                            pass
                        time.sleep(0.05)
                    else:
                        output.seek(0)
                        self.fail("Gunicorn did not become ready: " + output.read())
                yield base, child, output
            finally:
                if child.poll() is None:
                    child.terminate()
                try:
                    child.wait(timeout=12)
                except subprocess.TimeoutExpired:
                    child.kill()
                    child.wait(timeout=5)

    def token(self, base, email="owner@example.com"):
        result = requests.post(base + "/api/v1/auth/login", headers=HEADERS,
            json={"email": email, "password": PASSWORD}, timeout=5)
        self.assertEqual(result.status_code, 200, result.text)
        return result.json()["access_token"]

    def request(self, base, method, path, *, token=None, cookie=None, **kwargs):
        headers = dict(HEADERS)
        if token:
            headers["Authorization"] = "Bearer " + token
        if cookie:
            headers["Cookie"] = cookie
        return requests.request(method, base + path, headers=headers, allow_redirects=False, timeout=8, **kwargs)

    @patch("logging.config.fileConfig")
    def test_https_login_private_content_and_existing_websocket_flow(self, _logging):
        url = self.seed()
        with self.server(url) as (base, _, _):
            insecure = requests.get(base + "/learning/", headers={"Host": HEADERS["Host"]},
                                    allow_redirects=False, timeout=5)
            self.assertEqual(insecure.status_code, 302)
            self.assertTrue(insecure.headers["Location"].startswith("https://www.keithriordan.com/"))
            self.assertEqual(requests.get(base + "/", headers={**HEADERS, "Host": "untrusted.invalid"},
                                          timeout=5).status_code, 400)
            self.assertEqual(self.request(base, "GET", "/learning/").status_code, 302)
            self.assertEqual(self.request(base, "GET", API).status_code, 401)
            login = self.request(base, "GET", "/login?next=/learning/")
            self.assertNotIn("googletagmanager", login.text)
            self.assertNotIn("hotjar", login.text)
            csrf = re.search(r'name="csrf_token"[^>]*value="([^"]+)"', login.text).group(1)
            cookie = "session=" + login.cookies["session"]
            posted = self.request(base, "POST", "/login?next=/learning/", cookie=cookie,
                data={"email": "owner@example.com", "password": PASSWORD, "csrf_token": csrf, "remember_me": "y"})
            self.assertEqual(posted.status_code, 302)
            self.assertEqual(posted.headers["Location"], "/learning/")
            for header in posted.raw.headers.getlist("Set-Cookie"):
                self.assertIn("Secure", header)
                self.assertIn("HttpOnly", header)
                self.assertIn("SameSite=Lax", header)
            # Simulate cookies sent over HTTPS after TLS terminates at the router.
            cookie = "session=" + posted.cookies["session"]
            for path in ("/learning/", "/learning/concepts/idempotency", "/learning/concepts/idempotency/review"):
                response = self.request(base, "GET", path, cookie=cookie)
                self.assertEqual(response.status_code, 200, response.text[:500])
                self.assertIn("Private Learning pilot", response.text)
                self.assertIn("Draft idempotency content", response.text)
                self.assertNotIn("googletagmanager", response.text)
                self.assertNotIn("hotjar", response.text)
                self.assertEqual(response.headers["Cache-Control"], "private, no-store")
                self.assertEqual(response.headers["X-Learning-Content-Status"], "private-draft-pilot")
            self.assertEqual(self.request(base, "GET", API, cookie=cookie).status_code, 401)
            other = self.token(base, "other@example.com")
            self.assertEqual(self.request(base, "GET", API, token=other).status_code, 404)
            owner = self.token(base)
            # A native WebSocket upgrade and list acknowledgement through gthread,
            # for both the existing browser cookie and mobile JWT authentication.
            for authentication, socket_cookie in ((None, cookie), ({"token": owner}, None)):
                headers = ["X-Forwarded-Proto: https"]
                if socket_cookie:
                    headers.append("Cookie: " + socket_cookie)
                ws = websocket.create_connection(base.replace("http:", "ws:") + "/socket.io/?EIO=4&transport=websocket",
                    host=HEADERS["Host"], origin="https://www.keithriordan.com", header=headers, timeout=5)
                try:
                    self.assertTrue(ws.recv().startswith("0"))
                    ws.send("40" + (json.dumps(authentication) if authentication else ""))
                    self.assertTrue(ws.recv().startswith("40"))
                    ws.send('421["join_list",{"list_id":1}]')
                    reply = ws.recv()
                    self.assertTrue(reply.startswith("431"), reply)
                    self.assertTrue(json.loads(reply[3:])[0]["success"])
                finally:
                    ws.close()

    @patch("logging.config.fileConfig")
    def test_worker_saves_a_reply_and_restart_retains_work_and_spending(self, _logging):
        url = self.seed()
        with self.server(url, live=True) as (base, _, _):
            token = self.token(base)
            started = self.request(base, "POST", API, token=token,
                json={"exercise_id": "idempotent-order-api", "request_id": str(uuid4())})
            self.assertEqual(started.status_code, 201, started.text)
            sid = started.json()["session_id"]
            path = API + "/" + sid
            saved = self.request(base, "PUT", path + "/artifacts/api", token=token,
                json={"request_id": str(uuid4()), "base_revision": 0, "language": "text", "body": "POST /orders with key"})
            self.assertEqual(saved.status_code, 200, saved.text)
            sent = self.request(base, "POST", path + "/turns", token=token,
                json={"request_id": str(uuid4()), "body": "Do keys expire?", "expected_sequence": 1,
                      "artifact_revisions": {"api": 1, "schema": 0, "algorithm": 0}, "brief_revision": 0})
            self.assertEqual(sent.status_code, 202, sent.text)
            deadline = time.monotonic() + 15
            while time.monotonic() < deadline:
                detail = self.request(base, "GET", path, token=token).json()
                if detail["reply"]["status"] == "completed":
                    break
                time.sleep(0.1)
            else:
                self.fail("The real Gunicorn worker did not complete the fake reply: " + str(detail["reply"]))
            self.assertGreater(detail["ai_budget"]["total"]["spent_microusd"], approval()["carryover_microusd"])
        with self.server(url, live=True) as (base, _, _):
            recovered = self.request(base, "GET", path, token=token)
            self.assertEqual(recovered.status_code, 200)
            self.assertEqual(recovered.json(), detail)

    @patch("logging.config.fileConfig")
    def test_unmigrated_schema_and_unsafe_process_options_fail_before_serving(self, _logging):
        url = self.seed(ready=False)
        for options, expected in (((), "Database schema does not match"),
                                  (("--workers", "2"), "one threaded web process"),
                                  (("--preload",), "one threaded web process")):
            with self.subTest(options=options), self.server(url, options=options, must_boot=False) as (_, child, output):
                self.assertNotEqual(child.wait(timeout=15), 0)
                output.seek(0)
                self.assertIn(expected, output.read())
