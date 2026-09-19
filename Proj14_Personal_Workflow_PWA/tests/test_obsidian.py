import sys
import unittest
import urllib.error
from io import BytesIO
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from obsidian import Obsidian, ObsidianAuthError, ObsidianError  # noqa: E402


class FakeResponse:
    def __init__(self, body=b"", status=200):
        self._body = body
        self.status = status

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def http_error(code):
    return urllib.error.HTTPError(
        url="http://x", code=code, msg="err", hdrs=None, fp=BytesIO(b"body")
    )


class TestObsidian(unittest.TestCase):
    def setUp(self):
        self.api = Obsidian("http://127.0.0.1:27123", "tok")

    def test_read_returns_the_file_text(self):
        with mock.patch("urllib.request.urlopen",
                        return_value=FakeResponse(b"# Schedule\n")) as opened:
            self.assertEqual(self.api.read("Schedule.md"), "# Schedule\n")
        request = opened.call_args[0][0]
        self.assertEqual(request.get_method(), "GET")
        self.assertEqual(request.full_url, "http://127.0.0.1:27123/vault/Schedule.md")

    def test_read_sends_the_bearer_token(self):
        with mock.patch("urllib.request.urlopen",
                        return_value=FakeResponse(b"x")) as opened:
            self.api.read("Schedule.md")
        self.assertEqual(opened.call_args[0][0].get_header("Authorization"),
                         "Bearer tok")

    def test_read_returns_none_when_the_file_does_not_exist(self):
        with mock.patch("urllib.request.urlopen", side_effect=http_error(404)):
            self.assertIsNone(self.api.read("Missing.md"))

    def test_read_raises_auth_error_on_401(self):
        with mock.patch("urllib.request.urlopen", side_effect=http_error(401)):
            with self.assertRaises(ObsidianAuthError):
                self.api.read("Schedule.md")

    def test_read_raises_plain_error_on_500(self):
        with mock.patch("urllib.request.urlopen", side_effect=http_error(500)):
            with self.assertRaises(ObsidianError):
                self.api.read("Schedule.md")

    def test_write_puts_utf8_markdown(self):
        with mock.patch("urllib.request.urlopen",
                        return_value=FakeResponse(b"", 204)) as opened:
            self.api.write("Schedule.md", "# Schedule\n")
        request = opened.call_args[0][0]
        self.assertEqual(request.get_method(), "PUT")
        self.assertEqual(request.data, b"# Schedule\n")
        self.assertEqual(request.get_header("Content-type"), "text/markdown")

    def test_path_with_spaces_is_url_encoded(self):
        with mock.patch("urllib.request.urlopen",
                        return_value=FakeResponse(b"x")) as opened:
            self.api.read("Archive/My Note.md")
        self.assertIn("My%20Note.md", opened.call_args[0][0].full_url)

    def test_slashes_in_the_path_are_preserved(self):
        with mock.patch("urllib.request.urlopen",
                        return_value=FakeResponse(b"x")) as opened:
            self.api.read("Archive/Note.md")
        self.assertIn("/vault/Archive/Note.md", opened.call_args[0][0].full_url)


if __name__ == "__main__":
    unittest.main()
