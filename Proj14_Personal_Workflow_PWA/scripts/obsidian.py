"""Minimal client for the Obsidian Local REST API.

Same reasoning as couch.py and gcal.py: this project needs two calls against a
plain HTTP API, which urllib covers without adding a dependency to a repo that
deliberately has none.
"""
import urllib.error
import urllib.parse
import urllib.request


class ObsidianAuthError(Exception):
    """The API key is wrong or missing. Only a human fixes this."""


class ObsidianError(Exception):
    def __init__(self, status, body):
        super().__init__(f"Obsidian API returned {status}: {body}")
        self.status = status
        self.body = body


class Obsidian:
    def __init__(self, base_url, token):
        self.base_url = base_url.rstrip("/")
        self.token = token

    def _request(self, method, path, data=None, content_type=None):
        # safe="/" keeps folder separators intact while encoding spaces and
        # anything else that is not URL-safe in a note name.
        encoded = urllib.parse.quote(path, safe="/")
        req = urllib.request.Request(
            f"{self.base_url}/vault/{encoded}", data=data, method=method
        )
        req.add_header("Authorization", f"Bearer {self.token}")
        if content_type:
            req.add_header("Content-Type", content_type)
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                return resp.read()
        except urllib.error.HTTPError as exc:
            if exc.code in (401, 403):
                raise ObsidianAuthError(
                    "the Obsidian API key was rejected. Check OBSIDIAN_API_KEY "
                    "in schedule-app/.env against the Local REST API plugin."
                ) from exc
            raise ObsidianError(exc.code, exc.read().decode("utf-8", "replace")) from exc

    def read(self, path):
        """Return the note's text, or None if it does not exist."""
        try:
            return self._request("GET", path).decode("utf-8")
        except ObsidianError as exc:
            if exc.status == 404:
                return None
            raise

    def write(self, path, text):
        self._request("PUT", path, data=text.encode("utf-8"),
                      content_type="text/markdown")
