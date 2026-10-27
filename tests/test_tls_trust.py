"""Offline regression coverage for the eMudhra trust-store fix."""
import hashlib
import ssl
import unittest

import certifi
import httplib2
import requests
from botocore.httpsession import get_cert_path


class CertificateTrustTests(unittest.TestCase):
    def test_http_clients_reject_the_removed_emsign_root(self):
        compromised_root = "86a1ecba089c4a8d3bbe2734c612ba341d813e043cf9e8a862cd5c57a36bbe6b"
        for name, bundle in (
            ("requests", requests.certs.where()),
            ("httplib2", httplib2.CA_CERTS),
            ("botocore", get_cert_path(True)),
            ("certifi", certifi.where()),
        ):
            with self.subTest(client=name):
                context = ssl.create_default_context(cafile=bundle)
                fingerprints = {
                    hashlib.sha256(certificate).hexdigest()
                    for certificate in context.get_ca_certs(binary_form=True)
                }
                self.assertGreater(len(fingerprints), 50, "CA bundle unexpectedly empty")
                self.assertNotIn(compromised_root, fingerprints)
