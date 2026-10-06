"""Security regressions at the JWT and streamed HTTP integration boundaries."""

import base64
import http.client
import io
from pathlib import Path
import subprocess
import sys
import unittest
import zlib

import jwt
from flask_jwt_extended import create_access_token
from urllib3.exceptions import ProtocolError
from urllib3.response import HTTPResponse

from project import create_app
from project.sockets import socketio

SECRET = "test-signing-secret-with-at-least-32-bytes"


def segment(value):
    return base64.urlsafe_b64encode(value.encode()).rstrip(b"=").decode()


def chunked_response(body, headers=b""):
    class Socket:
        def makefile(self, *args, **kwargs):
            return io.BytesIO(
                b"HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\n"
                + headers + b"\r\n" + body
            )

    original = http.client.HTTPResponse(Socket(), method="GET")
    original.begin()
    return HTTPResponse(
        body=original, original_response=original,
        headers=dict(original.getheaders()), preload_content=False,
    )


def decode_chunked_deflate():
    expected = b"streamed screenshot content" * 40
    compressed = zlib.compress(expected)
    # Force compressed input across HTTP chunk boundaries and one-byte reads.
    wire = b"".join(b"1\r\n" + bytes([byte]) + b"\r\n" for byte in compressed)
    with chunked_response(wire + b"0\r\n\r\n", b"Content-Encoding: deflate\r\n") as response:
        assert b"".join(response.stream(amt=1, decode_content=True)) == expected


class DependencySecurityTests(unittest.TestCase):
    def test_unverified_decode_preserves_options_and_later_expiry_checks(self):
        token = jwt.encode({"exp": 1}, SECRET, algorithm="HS256")
        for decode in (jwt.decode, jwt.decode_complete):
            with self.subTest(decode=decode.__name__):
                options = {"verify_signature": False}
                decode(token, options=options)
                self.assertEqual(options, {"verify_signature": False})
                options["verify_signature"] = True
                with self.assertRaises(jwt.ExpiredSignatureError):
                    decode(token, SECRET, algorithms=["HS256"], options=options)

    def test_chunked_stream_round_trip(self):
        with chunked_response(b"3\r\nabc\r\n2\r\nde\r\n0\r\n\r\n") as response:
            self.assertEqual(b"".join(response.stream(amt=2)), b"abcde")

    def test_chunked_stream_rejects_unbounded_size_line(self):
        # A valid size followed by an oversized extension previously consumed
        # the entire line; rejecting it must not depend on invalid hex syntax.
        with chunked_response(b"1;" + b"a" * 100_000 + b"\r\nx\r\n0\r\n\r\n") as response:
            with self.assertRaisesRegex(ProtocolError, "chunk size line"):
                list(response.stream(amt=1))

    def test_fragmented_deflate_stream_terminates(self):
        # Bound the regression so reintroducing the infinite loop fails CI.
        subprocess.run(
            [sys.executable, "-c",
             "import runpy,sys; runpy.run_path(sys.argv[1])['decode_chunked_deflate']()",
             str(Path(__file__).resolve())],
            check=True, timeout=10, capture_output=True,
        )


class JWTBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app({
            "TESTING": True, "SECRET_KEY": SECRET, "JWT_SECRET_KEY": SECRET,
            "SQLALCHEMY_DATABASE_URI": "sqlite://", "WTF_CSRF_ENABLED": False,
        })

    def assert_token_rejected(self, token, status=422):
        response = self.app.test_client().get(
            "/api/v1/auth/me", base_url="https://localhost",
            headers={"Authorization": f"Bearer {token}"},
        )
        self.assertEqual(response.status_code, status)
        client = socketio.test_client(self.app, auth={"token": token})
        self.assertFalse(client.is_connected())

    def test_nested_unverified_header_and_payload_return_client_errors(self):
        nested = '[' * 2000 + '0' + ']' * 2000
        for header, payload in ((nested, '{}'), ('{"alg":"HS256"}', nested)):
            with self.subTest(header=header[:20]):
                self.assert_token_rejected(f"{segment(header)}.{segment(payload)}.AA")

    def test_expired_and_wrong_key_tokens_stay_rejected(self):
        with self.app.app_context():
            expired = create_access_token(identity="1", additional_claims={"exp": 1})
        self.assert_token_rejected(expired, 401)
        forged = jwt.encode({"sub": "1", "type": "access"}, SECRET + "wrong", algorithm="HS256")
        self.assert_token_rejected(forged)
