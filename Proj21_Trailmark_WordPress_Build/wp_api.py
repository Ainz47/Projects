"""Shared WordPress REST helper for the Trailmark demo scripts.

Auth: the WP application password used by the EMCP MCP server, read from
~/.claude.json at run time and never printed.
"""
import json
import sys
from pathlib import Path

import requests


def _creds():
    cfg = json.loads((Path.home() / ".claude.json").read_text(encoding="utf-8"))
    for proj in cfg.get("projects", {}).values():
        srv = proj.get("mcpServers", {}).get("emcp-demo")
        if srv:
            env = srv["env"]
            return env["WP_URL"].rstrip("/"), (env["WP_USERNAME"], env["WP_APP_PASSWORD"])
    sys.exit("emcp-demo server config not found in ~/.claude.json")


BASE, _AUTH = _creds()
SESSION = requests.Session()
SESSION.auth = _AUTH


def api(method, path, **kw):
    r = SESSION.request(method, f"{BASE}/wp-json/{path}", timeout=60, **kw)
    if r.status_code >= 400:
        print(f"{method} {path} -> {r.status_code}: {r.text[:400]}")
        sys.exit(1)
    return r.json()


class State:
    """Small JSON file of ids a script created, so reruns update instead of duplicating."""

    def __init__(self, path):
        self.path = Path(path)
        self.data = json.loads(self.path.read_text()) if self.path.exists() else {}

    def __getitem__(self, k):
        return self.data[k]

    def __contains__(self, k):
        return k in self.data

    def __setitem__(self, k, v):
        self.data[k] = v
        self.path.write_text(json.dumps(self.data, indent=2))
