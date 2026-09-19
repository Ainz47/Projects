"""Minimal CouchDB client over the standard library.

No requests, no couchdb package. The API surface used by this project is four
verbs against JSON, which urllib covers without adding a dependency to a repo
whose whole point is that it has none.
"""
import base64
import json
import urllib.error
import urllib.request
from pathlib import Path


def load_env(path):
    """Parse a simple KEY=VALUE .env file. Blank lines and # comments ignored."""
    env = {}
    p = Path(path)
    if not p.exists():
        raise SystemExit(f"missing {p}. Copy .env.example to .env and fill it in.")
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        env[key.strip()] = value.strip()
    return env


class CouchError(Exception):
    def __init__(self, status, body):
        super().__init__(f"CouchDB returned {status}: {body}")
        self.status = status
        self.body = body


class CouchDB:
    def __init__(self, base_url, user, password):
        self.base_url = base_url.rstrip("/")
        token = base64.b64encode(f"{user}:{password}".encode("utf-8")).decode("ascii")
        self.auth_header = f"Basic {token}"

    def request(self, method, path, body=None):
        url = f"{self.base_url}/{path.lstrip('/')}"
        data = json.dumps(body).encode("utf-8") if body is not None else None
        req = urllib.request.Request(url, data=data, method=method)
        req.add_header("Authorization", self.auth_header)
        req.add_header("Accept", "application/json")
        if data is not None:
            req.add_header("Content-Type", "application/json")
        try:
            with urllib.request.urlopen(req) as resp:
                raw = resp.read().decode("utf-8")
                return resp.status, (json.loads(raw) if raw else {})
        except urllib.error.HTTPError as exc:
            raw = exc.read().decode("utf-8", "replace")
            return exc.code, (json.loads(raw) if raw.startswith("{") else {"error": raw})

    def ensure_db(self, name):
        # PUT /{db} is a server-admin-only endpoint in CouchDB: a caller that is
        # only a db admin (the schedule_app account, scoped to this one database
        # on purpose) gets 401 here even when the database already exists, before
        # CouchDB ever checks existence. So 401 is not necessarily a failure —
        # fall back to a plain read, which db-admin rights do cover, and only
        # raise if the database is actually missing.
        status, _ = self.request("PUT", f"/{name}")
        if status in (201, 412):          # created, or already there
            return status == 201
        if status == 401:
            check_status, _ = self.request("GET", f"/{name}")
            if check_status == 200:
                return False              # already there; this caller just can't create dbs
        raise CouchError(status, f"could not create database {name}")

    def get_doc(self, db, doc_id):
        status, body = self.request("GET", f"/{db}/{urllib.request.quote(doc_id, safe='')}")
        if status == 200:
            return body
        if status == 404:
            return None
        raise CouchError(status, body)

    def put_doc(self, db, doc):
        """Write a document, carrying forward the current _rev if one exists."""
        existing = self.get_doc(db, doc["_id"])
        if existing:
            doc = dict(doc, _rev=existing["_rev"])
        status, body = self.request(
            "PUT", f"/{db}/{urllib.request.quote(doc['_id'], safe='')}", doc
        )
        if status not in (201, 202):
            raise CouchError(status, body)
        return body
