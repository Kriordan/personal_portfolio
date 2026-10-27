"""Anonymous TLS checks; never imports the application or reads its .env.

Run with the deployed application's Python environment. Network failures are
inconclusive and fail the check; only certificate rejection counts as a pass.
"""
import json
import platform
import socket
import ssl
import sys

import certifi
import httplib2
import requests
from botocore.awsrequest import AWSPreparedRequest
from botocore.httpsession import URLLib3Session, get_cert_path

CONTROL = "www.python.org"
COMPROMISED = (
    "dv-g3b-emudhra.we-have-a-problem.com",
    "dv-g3b-aaa-emudhra.we-have-a-problem.com",
)


def system_tls(host):
    with socket.create_connection((host, 443), timeout=8) as connection:
        with ssl.create_default_context().wrap_socket(connection, server_hostname=host):
            pass


def requests_tls(host):
    with requests.Session() as client:
        with client.head("https://" + host + "/", timeout=8, allow_redirects=False):
            pass


def httplib2_tls(host):
    client = httplib2.Http(timeout=8)
    try:
        client.request("https://" + host + "/", method="HEAD", redirections=0)
    finally:
        client.close()


def botocore_tls(host):
    client = URLLib3Session(timeout=8)
    try:
        response = client.send(AWSPreparedRequest(
            method="HEAD", url="https://" + host + "/", headers={},
            body=None, stream_output=True,
        ))
        response.raw.close()
    finally:
        client.close()


def main():
    print(json.dumps({
        "python": platform.python_version(), "certifi": certifi.__version__,
        "httplib2_uses_certifi": httplib2.CA_CERTS == certifi.where(),
        "botocore_uses_certifi": get_cert_path(True) == certifi.where(),
    }))
    passed = True
    for name, check in (
        ("system", system_tls), ("requests", requests_tls),
        ("httplib2", httplib2_tls), ("botocore", botocore_tls),
    ):
        for host in (CONTROL, *COMPROMISED):
            try:
                check(host)
                result = "accepted"
            except Exception as error:
                result = ("certificate_rejected" if "CERTIFICATE_VERIFY_FAILED" in str(error)
                          else "inconclusive:" + type(error).__name__)
            expected = "accepted" if host == CONTROL else "certificate_rejected"
            passed &= result == expected
            print(json.dumps({"client": name, "host": host, "result": result,
                              "pass": result == expected}), flush=True)
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
