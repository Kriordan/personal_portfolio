"""The Learning OpenAI call, run for real in its child process against a local fake server.

No database, Flask app, or network: the fake Responses API listens on 127.0.0.1 and the key
is a test value. Each case checks the fixed code and what the ledger would record.
"""
import ast
import contextlib
import json
import os
import shlex
import signal
import socket
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest.mock import patch

import requests

from project import learning_ai_call as child
from project.services import learning_ai_provider as provider_module
from project.services.learning_ai_provider import SCRIPT, OpenAIProvider, ProviderError, child_environment

KEY = provider_module.KEY_VARIABLE
TEST_KEY = "learning-test-key-fixture"
BODY = {
    "model": "fake-interviewer", "store": False, "service_tier": "default", "max_output_tokens": 1200,
    "instructions": "Ask one focused question at a time.", "input": json.dumps({"transcript": ["Hello"]}),
    "text": {"format": {"type": "json_schema", "name": "interviewer_reply", "strict": True, "schema": {
        "type": "object", "properties": {"reply": {"type": "string"}}, "required": ["reply"],
        "additionalProperties": False}}},
}
USAGE = {"input_tokens": 120, "input_tokens_details": {"cached_tokens": 64}, "output_tokens": 30,
         "output_tokens_details": {"reasoning_tokens": 8}, "total_tokens": 150}
LEDGER_USAGE = {"input_tokens": 120, "cached_input_tokens": 64, "cache_write_tokens": 0, "output_tokens": 30}


def response(text=None, *, status="completed", parts=None):
    """A Responses API body: a reasoning item, then a message holding `text` (or `parts`)."""
    content = parts if parts is not None else [{"type": "output_text", "text": text, "annotations": []}]
    return {"id": "resp_fixture", "object": "response", "status": status, "usage": USAGE,
            "output": [{"type": "reasoning", "id": "rs_fixture", "summary": []},
                       {"type": "message", "id": "msg_fixture", "role": "assistant", "content": content}]}


class FakeResponses(BaseHTTPRequestHandler):
    """Answers each POST as the running test scripted it, and records the request."""

    def do_POST(self):
        server, script = self.server, self.server.script
        body = self.rfile.read(int(self.headers.get("Content-Length", 0)))
        server.received.append({"path": self.path, "headers": dict(self.headers), "body": json.loads(body)})
        if server.release.wait(script.get("delay", 0)):
            return
        payload = script.get("raw") or json.dumps(script.get("json", {})).encode()
        self.send_response(script.get("status", 200))
        self.send_header("Content-Type", script.get("type", "application/json"))
        self.send_header("Content-Length", str(len(payload)))
        for name, value in script.get("headers", {}).items():
            self.send_header(name, value)
        self.end_headers()
        if not script.get("trickle"):
            self.wfile.write(payload)
            return
        for byte in payload:  # Each byte inside the read timeout, so only the total deadline stops it.
            if server.release.wait(script["trickle"]):
                return
            self.wfile.write(bytes([byte]))

    def log_message(self, *args):
        pass


class FakeServer(ThreadingHTTPServer):
    block_on_close = False  # A handler still waiting out a delay never holds up the tests.

    def handle_error(self, request, client_address):
        pass  # A child killed mid-response is expected.


class LearningAICallTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = FakeServer(("127.0.0.1", 0), FakeResponses)
        cls.server.release, cls.server.script, cls.server.received = threading.Event(), {}, []
        cls.base_url = f"http://127.0.0.1:{cls.server.server_port}/v1"
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.server.release.set()
        cls.server.shutdown()
        cls.server.server_close()

    def setUp(self):
        self.server.script, self.server.received = {}, []
        self.enterContext(patch.dict(os.environ, {KEY: TEST_KEY}))
        self.provider = OpenAIProvider(base_url=self.base_url)

    def respond(self, **script):
        self.server.script = script

    def call_error(self, provider=None, *, body=BODY, deadline=10):
        with self.assertRaises(ProviderError) as caught:
            (provider or self.provider).call(body, deadline=deadline)
        return caught.exception

    @contextlib.contextmanager
    def recording(self):
        """Run the real child, keeping each finished process for inspection."""
        real_run, finished = subprocess.run, []

        def run(*args, **kwargs):
            finished.append(real_run(*args, **kwargs))
            return finished[-1]

        with patch.object(provider_module.subprocess, "run", side_effect=run):
            yield finished

    def test_text_beyond_ascii_reaches_the_provider_and_comes_back_intact(self):
        text = "Ünïcode — 注文 ✓ 🚀"
        self.respond(json=response(json.dumps({"reply": text}, ensure_ascii=False)))
        body = dict(BODY, input=json.dumps({"transcript": [text]}, ensure_ascii=False))
        self.assertEqual(self.provider.call(body, deadline=10)["output"], {"reply": text})
        self.assertEqual(self.server.received[0]["body"]["input"], body["input"])

    def test_success_returns_output_usage_and_timing_and_sends_the_body_unchanged(self):
        self.respond(json=response(json.dumps({"reply": "What happens when the same order arrives twice?"})))
        with self.recording() as finished:
            result = self.provider.call(BODY, deadline=10)
        self.assertEqual((finished[0].returncode, finished[0].stdout.count("\n")), (0, 1))
        self.assertEqual(set(json.loads(finished[0].stdout)), {"output", "usage", "seconds"})
        self.assertEqual(result["output"], {"reply": "What happens when the same order arrives twice?"})
        self.assertEqual(result["usage"], LEDGER_USAGE)
        self.assertGreaterEqual(result["seconds"], 0)
        self.assertGreaterEqual(result["spawn_seconds"], 0)
        [request] = self.server.received
        self.assertEqual(request["path"], "/v1/responses")
        self.assertEqual(request["headers"]["Authorization"], "Bearer " + TEST_KEY)
        self.assertEqual(request["body"], BODY)
        sent = request["body"]
        self.assertIs(sent["store"], False)
        self.assertEqual(sent["service_tier"], "default")
        self.assertEqual((sent["text"]["format"]["type"], sent["text"]["format"]["strict"]), ("json_schema", True))
        self.assertNotIn("tools", sent)

    def test_refusal_incomplete_and_invalid_output_are_charged_and_keep_usage(self):
        cases = [
            (response(parts=[{"type": "refusal", "refusal": "I can't help with that."}]), "refused", "yes"),
            (response('{"reply": "What abo', status="incomplete"), "incomplete", "yes"),
            (response("What happens on retry?"), "invalid_output", "yes"),
            (response('["a JSON array"]'), "invalid_output", "yes"),
            (response(parts=[]), "invalid_output", "yes"),
            (response('{"reply": "x"}', status="failed"), "provider", "unknown"),
        ]
        for payload, code, charged in cases:
            with self.subTest(code=code, status=payload["status"]), self.recording() as finished:
                self.respond(json=payload)
                error = self.call_error()
                self.assertEqual((error.code, error.charged, error.usage), (code, charged, LEDGER_USAGE))
                self.assertEqual((finished[0].returncode, finished[0].stdout.count("\n")), (1, 1))
                self.assertEqual(set(json.loads(finished[0].stdout)), {"error", "charged", "usage", "seconds"})

    def test_http_errors_say_whether_the_call_was_charged(self):
        cases = [(400, "provider_request", "no"), (401, "provider_auth", "no"), (402, "provider_quota", "no"),
                 (403, "provider_auth", "no"), (404, "provider_request", "no"), (429, "provider_quota", "no"),
                 (408, "timeout", "unknown"), (409, "failed", "unknown"), (500, "provider", "unknown"),
                 (503, "provider", "unknown"), (504, "timeout", "unknown")]
        for status, code, charged in cases:
            with self.subTest(status=status):
                self.respond(status=status, json={"error": {"message": "Incorrect API key provided: " + TEST_KEY}})
                error = self.call_error()
                self.assertEqual((error.code, error.charged, error.usage), (code, charged, None))
                self.assertEqual(error.args, (code,))

    def test_redirects_are_not_followed(self):
        self.respond(status=307, headers={"Location": self.base_url + "/responses/elsewhere"})
        error = self.call_error()
        self.assertEqual((error.code, error.charged), ("failed", "unknown"))
        self.assertEqual([request["path"] for request in self.server.received], ["/v1/responses"])

    def test_a_200_that_is_not_a_bounded_json_object_is_uncertain(self):
        for script in ({"type": "text/html", "raw": b"<html>Busy</html>"}, {"raw": b'{"status": "compl'}):
            with self.subTest(script=script):
                self.respond(**script)
                error = self.call_error()
                self.assertEqual((error.code, error.charged, error.usage), ("provider", "unknown", None))
        self.respond(json={**response('{"reply": "x"}'), "padding": "x" * 5000})
        error = self.call_error(OpenAIProvider(base_url=self.base_url, max_response_bytes=4096))
        self.assertEqual((error.code, error.charged, error.usage), ("too_large", "unknown", None))

    def test_a_provider_slower_than_the_deadline_times_out(self):
        self.respond(delay=10, json=response('{"reply": "Too late."}'))
        started = time.monotonic()
        error = self.call_error(deadline=1)
        self.assertEqual((error.code, error.charged), ("timeout", "unknown"))
        self.assertLess(time.monotonic() - started, 5)

    def test_the_alarm_ends_a_response_that_trickles_past_the_deadline(self):
        self.respond(trickle=0.05, json=response('{"reply": "Slowly."}'))
        with self.recording() as finished:
            error = self.call_error(deadline=1)
        self.assertEqual((error.code, error.charged), ("timeout", "unknown"))
        self.assertEqual(finished[0].returncode, -signal.SIGALRM)

    def test_a_refused_connection_is_uncertain(self):
        with socket.socket() as probe:
            probe.bind(("127.0.0.1", 0))
            port = probe.getsockname()[1]
        error = self.call_error(OpenAIProvider(base_url=f"http://127.0.0.1:{port}/v1"))
        self.assertEqual((error.code, error.charged), ("provider", "unknown"))

    def test_a_missing_key_fails_without_starting_a_child(self):
        del os.environ[KEY]
        with patch.object(provider_module.subprocess, "run") as run:
            error = self.call_error()
        self.assertEqual((error.code, error.charged, error.usage), ("provider_auth", "no", None))
        run.assert_not_called()

    def test_plain_http_is_refused_unless_local_before_any_request(self):
        port = self.server.server_port
        # Each would reach only this machine, with no DNS lookup, if the check were broken.
        for base_url in (f"http://127.0.0.2:{port}/v1", f"http://127.1:{port}/v1", f"http://user@127.0.0.1:{port}/v1",
                         "http://localhost/v1", f"ftp://127.0.0.1:{port}/v1", f"http://127.0.0.1:{port}/v1?x=1"):
            with self.subTest(base_url=base_url):
                error = self.call_error(OpenAIProvider(base_url=base_url))
                self.assertEqual((error.code, error.charged), ("failed", "no"))
        self.assertEqual(self.server.received, [])
        # The rule itself, for hosts a test must never contact.
        for base_url in ("http://api.openai.com/v1", "http://127.0.0.1.example.com:80/v1", "http://localhost.:80/v1",
                         "http://example.com\\@127.0.0.1:80/v1", "https://user:pw@api.openai.com/v1", "https:///v1"):
            self.assertFalse(child.allowed_base(base_url), base_url)
        for base_url in ("https://api.openai.com/v1", "http://localhost:8080/v1", self.base_url):
            self.assertTrue(child.allowed_base(base_url), base_url)

    def test_a_request_over_the_input_cap_is_refused_before_sending(self):
        error = self.call_error(body=dict(BODY, input="x" * child.MAX_INPUT_BYTES))
        self.assertEqual((error.code, error.charged), ("failed", "no"))
        # Valid JSON padded past the cap: only the cap itself refuses it, not a truncated parse.
        payload = json.dumps({"parent_pid": os.getpid(), "deadline": 5, "base_url": self.base_url, "body": BODY,
                              "max_response_bytes": 1000})
        ran = subprocess.run([sys.executable, "-I", str(SCRIPT)], input=payload.ljust(child.MAX_INPUT_BYTES + 1),
                             env=child_environment(), capture_output=True, text=True, timeout=30)
        self.assertEqual(json.loads(ran.stdout), {"error": "failed", "charged": "no", "usage": None, "seconds": 0.0})
        self.assertEqual(self.server.received, [])

    def test_the_child_environment_holds_only_the_key_path_and_ca_settings(self):
        parent = {KEY: TEST_KEY, "PATH": "/usr/bin:/bin", "SSL_CERT_FILE": "/etc/ssl/cert.pem",
                  "REQUESTS_CA_BUNDLE": "", "LEARNING_TEST_SENTINEL": "leak", "DATABASE_URL": "postgresql://user:pw@db/app",
                  "OPENAI_API_KEY": "jobwizard-key", "PYTHONPATH": "/elsewhere", "HOME": "/home/learner"}
        self.assertEqual(child_environment(parent), {KEY: TEST_KEY, "PATH": "/usr/bin:/bin",
                                                     "SSL_CERT_FILE": "/etc/ssl/cert.pem"})
        os.environ.update(LEARNING_TEST_SENTINEL="leak", DATABASE_URL="postgresql://user:pw@db/app")
        self.respond(json=response('{"reply": "Fine."}'))
        with patch.object(provider_module.subprocess, "run", wraps=subprocess.run) as run:
            self.assertEqual(self.provider.call(BODY, deadline=10)["output"], {"reply": "Fine."})
        args, kwargs = run.call_args
        self.assertEqual(args[0], [sys.executable, "-I", str(SCRIPT)])
        self.assertEqual((kwargs["env"][KEY], kwargs["env"]["PATH"]), (TEST_KEY, os.environ["PATH"]))
        self.assertLessEqual(set(kwargs["env"]), {KEY, "PATH", *provider_module.CA_VARIABLES})
        self.assertEqual((kwargs["timeout"], kwargs["stderr"]), (15, subprocess.DEVNULL))

    def test_the_child_imports_only_the_standard_library_and_requests(self):
        tree = ast.parse(SCRIPT.read_text())
        names = {alias.name for node in ast.walk(tree) if isinstance(node, ast.Import) for alias in node.names}
        names |= {node.module or "." for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)}
        self.assertEqual({name.split(".")[0] for name in names} - set(sys.stdlib_module_names), {"requests"})
        # Outside the repository, with nothing but PATH: it loads, and without a key stops before any request.
        probe = ("import runpy, sys; runpy.run_path(sys.argv[1]); "
                 "print(' '.join({name.split('.')[0] for name in sys.modules}))")
        payload = {"parent_pid": os.getpid(), "deadline": 5, "base_url": self.base_url, "body": BODY,
                   "max_response_bytes": 1000}
        with tempfile.TemporaryDirectory() as folder:
            options = dict(cwd=folder, env={"PATH": os.environ["PATH"]}, capture_output=True, text=True, timeout=30)
            loaded = subprocess.run([sys.executable, "-I", "-c", probe, str(SCRIPT)], **options)
            ran = subprocess.run([sys.executable, "-I", str(SCRIPT)], input=json.dumps(payload), **options)
        self.assertEqual(loaded.returncode, 0)
        self.assertIn("requests", loaded.stdout.split())
        self.assertFalse({"project", "flask", "dotenv", "boto3", "botocore", "sqlalchemy"} & set(loaded.stdout.split()))
        self.assertEqual((ran.returncode, json.loads(ran.stdout)),
                         (1, {"error": "provider_auth", "charged": "no", "usage": None, "seconds": 0.0}))
        self.assertEqual(self.server.received, [])

    def test_the_childs_stderr_is_discarded(self):
        self.respond(json=response('{"reply": "Fine."}'))
        with tempfile.TemporaryDirectory() as folder, tempfile.TemporaryFile() as captured:
            python = os.path.join(folder, "python")
            with open(python, "w") as file:
                file.write(f'#!/bin/sh\necho "child stderr sentinel" >&2\nexec {shlex.quote(sys.executable)} "$@"\n')
            os.chmod(python, 0o700)
            saved = os.dup(2)
            os.dup2(captured.fileno(), 2)
            try:
                result = OpenAIProvider(base_url=self.base_url, python=python).call(BODY, deadline=10)
            finally:
                os.dup2(saved, 2)
                os.close(saved)
            captured.seek(0)
            self.assertNotIn(b"sentinel", captured.read())
        self.assertEqual(result["output"], {"reply": "Fine."})

    def test_the_parent_maps_what_the_child_reports(self):
        def finished(returncode, stdout):
            return subprocess.CompletedProcess([], returncode, stdout=stdout)

        reported = {"error": "refused", "charged": "yes", "usage": LEDGER_USAGE, "seconds": 0.5}
        cases = [
            (finished(-signal.SIGALRM, ""), ("timeout", "unknown", None)),
            (finished(-signal.SIGKILL, ""), ("timeout", "unknown", None)),
            (finished(1, "Traceback (most recent call last):"), ("failed", "unknown", None)),
            (finished(0, "[]"), ("failed", "unknown", None)),
            (finished(1, json.dumps(reported)), ("refused", "yes", LEDGER_USAGE)),
            (finished(1, json.dumps({"error": "novel", "charged": "maybe", "usage": {"input_tokens": -1}})),
             ("failed", "unknown", None)),
            # Usage from an older child, without cache writes, isn't trusted: the reservation stands.
            (finished(1, json.dumps({**reported, "usage": {"input_tokens": 120, "cached_input_tokens": 64,
                                                           "output_tokens": 30}})), ("refused", "yes", None)),
            (finished(1, json.dumps({**reported, "usage": {**LEDGER_USAGE, "cache_write_tokens": 57}})),
             ("refused", "yes", None)),  # 64 cached + 57 written > 120 input
            (finished(1, json.dumps({**reported, "usage": {**LEDGER_USAGE, "cache_write_tokens": 56}})),
             ("refused", "yes", {**LEDGER_USAGE, "cache_write_tokens": 56})),
            (finished(1, json.dumps({"error": ["refused"], "charged": {"no": 1}})), ("failed", "unknown", None)),
            (finished(1, json.dumps({"output": {"reply": "x"}, "usage": None, "seconds": 0.1})),
             ("failed", "unknown", None)),
        ]
        for outcome, expected in cases:
            with self.subTest(returncode=outcome.returncode, stdout=outcome.stdout):
                with patch.object(provider_module.subprocess, "run", return_value=outcome):
                    error = self.call_error()
                self.assertEqual((error.code, error.charged, error.usage), expected)
        for raised, expected in ((subprocess.TimeoutExpired("python", 15), "timeout"), (FileNotFoundError(), "failed")):
            with patch.object(provider_module.subprocess, "run", side_effect=raised) as run:
                error = self.call_error()
            self.assertEqual((error.code, error.charged), (expected, "unknown"))
            self.assertEqual(run.call_args.kwargs["timeout"], 15)

    def test_the_child_reads_usage_and_exceptions_conservatively(self):
        self.assertEqual(child.usage_of({"usage": {"input_tokens": 5, "output_tokens": 2}}),
                         {"input_tokens": 5, "cached_input_tokens": 0, "cache_write_tokens": 0, "output_tokens": 2})
        # Cached reads and cache writes are separate parts of the input.
        written = {"input_tokens": 9, "input_tokens_details": {"cached_tokens": 3, "cache_write_tokens": 6},
                   "output_tokens": 2}
        self.assertEqual(child.usage_of({"usage": written}),
                         {"input_tokens": 9, "cached_input_tokens": 3, "cache_write_tokens": 6, "output_tokens": 2})
        for usage in ({"input_tokens": 5, "input_tokens_details": {"cached_tokens": 6}, "output_tokens": 2},
                      {"input_tokens": 9, "input_tokens_details": {"cached_tokens": 4, "cache_write_tokens": 6},
                       "output_tokens": 2},
                      {"input_tokens": 9, "input_tokens_details": {"cache_write_tokens": -1}, "output_tokens": 2},
                      {"input_tokens": 9, "input_tokens_details": {"cache_write_tokens": "6"}, "output_tokens": 2},
                      {"input_tokens": 5, "output_tokens": -1}, {"input_tokens": 5.0, "output_tokens": 2},
                      {"input_tokens": True, "output_tokens": 2}, {"output_tokens": 2}, None, "lots"):
            self.assertIsNone(child.usage_of({"usage": usage}), usage)
        cases = [(requests.exceptions.ConnectTimeout(), True, ("timeout", "no")),
                 (requests.exceptions.ReadTimeout(), True, ("timeout", "unknown")),
                 (requests.exceptions.ConnectionError(), True, ("provider", "unknown")),
                 (requests.exceptions.SSLError(), True, ("provider", "unknown")),
                 (RuntimeError("Bearer " + TEST_KEY), True, ("failed", "unknown")),
                 (KeyError("base_url"), False, ("failed", "no"))]
        for error, sent, expected in cases:
            self.assertEqual(child.failure(error, sent=sent), expected, repr(error))


if __name__ == "__main__":
    unittest.main()
