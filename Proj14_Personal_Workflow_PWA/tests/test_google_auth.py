"""Security-critical parts of the one-time OAuth helper.

The interactive flow itself cannot be unit tested, but the PKCE derivation
and the state comparison are pure and are exactly the parts that must not
be subtly wrong.
"""
import base64
import hashlib
import sys
import unittest
import urllib.parse
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import google_auth  # noqa: E402


class TestPkce(unittest.TestCase):
    def test_challenge_is_unpadded_base64url_sha256_of_the_verifier(self):
        verifier, challenge = google_auth._pkce_pair()
        expected = base64.urlsafe_b64encode(
            hashlib.sha256(verifier.encode("ascii")).digest()
        ).decode("ascii").rstrip("=")
        self.assertEqual(challenge, expected)

    def test_challenge_carries_no_padding_and_is_url_safe(self):
        _, challenge = google_auth._pkce_pair()
        self.assertNotIn("=", challenge)
        self.assertNotIn("+", challenge)
        self.assertNotIn("/", challenge)

    def test_each_run_mints_a_fresh_verifier(self):
        first, _ = google_auth._pkce_pair()
        second, _ = google_auth._pkce_pair()
        self.assertNotEqual(first, second)

    def test_verifier_meets_the_rfc_7636_length_floor(self):
        verifier, _ = google_auth._pkce_pair()
        self.assertGreaterEqual(len(verifier), 43)
        self.assertLessEqual(len(verifier), 128)


class TestRedirectContract(unittest.TestCase):
    def test_redirect_uri_is_loopback_only(self):
        parsed = urllib.parse.urlparse(google_auth.REDIRECT_URI)
        self.assertEqual(parsed.hostname, "127.0.0.1")
        self.assertEqual(parsed.scheme, "http")

    def test_scope_is_limited_to_calendar(self):
        self.assertEqual(google_auth.SCOPE,
                         "https://www.googleapis.com/auth/calendar")


if __name__ == "__main__":
    unittest.main()
