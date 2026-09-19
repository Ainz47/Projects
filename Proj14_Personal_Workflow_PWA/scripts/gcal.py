"""Minimal Google Calendar client over the standard library.

Same reasoning as couch.py: the API surface this project needs is a token
refresh plus five calls against JSON, which urllib covers without adding a
dependency tree to a repo that deliberately has none.
"""
import json
import urllib.error
import urllib.parse
import urllib.request

TOKEN_URL = "https://oauth2.googleapis.com/token"
API = "https://www.googleapis.com/calendar/v3"


class GoogleAuthError(Exception):
    """The refresh token is dead. Only a human re-consenting fixes this."""


class GoogleApiError(Exception):
    def __init__(self, status, body):
        super().__init__(f"Google API returned {status}: {body}")
        self.status = status
        self.body = body


def access_token(client_id, client_secret, refresh_token):
    """Exchange the long-lived refresh token for a short-lived access token."""
    body = urllib.parse.urlencode({
        "client_id": client_id,
        "client_secret": client_secret,
        "refresh_token": refresh_token,
        "grant_type": "refresh_token",
    }).encode("utf-8")
    req = urllib.request.Request(TOKEN_URL, data=body, method="POST")
    req.add_header("Content-Type", "application/x-www-form-urlencoded")
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read().decode("utf-8"))["access_token"]
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", "replace")
        # invalid_grant is the one failure a retry can never fix: the token was
        # revoked, expired through disuse, or the consent screen was reset.
        if exc.code == 400 and "invalid_grant" in raw:
            raise GoogleAuthError(
                "the Google refresh token is no longer valid. "
                "Run: py scripts/google_auth.py"
            ) from exc
        raise GoogleApiError(exc.code, raw) from exc


def paged(fetch_page):
    """Collect items across every page. fetch_page(token) returns one response."""
    items = []
    token = None
    while True:
        page = fetch_page(token)
        items.extend(page.get("items", []))
        token = page.get("nextPageToken")
        if not token:
            return items


class GoogleCalendar:
    def __init__(self, token):
        self.token = token

    def request(self, method, path, body=None, params=None):
        url = f"{API}{path}"
        if params:
            url = f"{url}?{urllib.parse.urlencode(params)}"
        data = json.dumps(body).encode("utf-8") if body is not None else None
        req = urllib.request.Request(url, data=data, method=method)
        req.add_header("Authorization", f"Bearer {self.token}")
        req.add_header("Accept", "application/json")
        if data is not None:
            req.add_header("Content-Type", "application/json")
        try:
            with urllib.request.urlopen(req) as resp:
                raw = resp.read().decode("utf-8")
                return json.loads(raw) if raw else {}
        except urllib.error.HTTPError as exc:
            raise GoogleApiError(exc.code, exc.read().decode("utf-8", "replace")) from exc

    def find_calendar(self, name):
        """Return the id of the calendar with this exact summary, or None."""
        entries = paged(lambda token: self.request(
            "GET", "/users/me/calendarList",
            params={"pageToken": token} if token else None,
        ))
        for entry in entries:
            if entry.get("summary") == name:
                return entry["id"]
        return None

    def create_calendar(self, name, timezone):
        created = self.request("POST", "/calendars",
                               body={"summary": name, "timeZone": timezone})
        return created["id"]

    def list_events(self, calendar_id, time_min, time_max):
        encoded = urllib.parse.quote(calendar_id, safe="")

        def fetch(token):
            params = {
                "timeMin": time_min,
                "timeMax": time_max,
                "singleEvents": "true",
                "maxResults": "2500",
            }
            if token:
                params["pageToken"] = token
            return self.request("GET", f"/calendars/{encoded}/events", params=params)

        return paged(fetch)

    def insert_event(self, calendar_id, body):
        encoded = urllib.parse.quote(calendar_id, safe="")
        return self.request("POST", f"/calendars/{encoded}/events", body=body)

    def update_event(self, calendar_id, event_id, body):
        encoded = urllib.parse.quote(calendar_id, safe="")
        return self.request("PUT", f"/calendars/{encoded}/events/{event_id}", body=body)

    def delete_event(self, calendar_id, event_id):
        encoded = urllib.parse.quote(calendar_id, safe="")
        self.request("DELETE", f"/calendars/{encoded}/events/{event_id}")
