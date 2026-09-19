"""Upload src/ and vendor/ as attachments on _design/app.

One PUT with every attachment inlined, so a deploy is atomic: either the whole
app updates or none of it does. Uploading attachments one at a time would leave
the app briefly serving a mix of old and new files, and would need a fresh _rev
for each upload.
"""
import base64
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from couch import CouchDB, load_env  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
DESIGN_ID = "_design/app"

CONTENT_TYPES = {
    ".html": "text/html",
    ".js": "text/javascript",
    ".css": "text/css",
    ".json": "application/json",
    ".svg": "image/svg+xml",
}

# Directories whose contents become attachments, and the attachment name prefix
# each one gets. src/index.html becomes "index.html"; vendor/pouchdb.min.js
# becomes "vendor/pouchdb.min.js".
SOURCES = [("src", ""), ("vendor", "vendor/")]

# The pure modules are tested under Node and shipped to the browser unchanged,
# but their tests and fixtures are not part of the app.
SKIP_DIRS = {"__pycache__"}


def collect():
    attachments = {}
    for folder, prefix in SOURCES:
        base = ROOT / folder
        # vendor/ does not exist until PouchDB is vendored in Task 5; a source
        # dir that is not there yet is skipped, not fatal. The index.html guard
        # in main() is what actually refuses an empty or broken deploy.
        if not base.exists():
            continue
        for path in sorted(base.rglob("*")):
            if not path.is_file():
                continue
            if any(part in SKIP_DIRS for part in path.parts):
                continue
            suffix = path.suffix.lower()
            if suffix not in CONTENT_TYPES:
                continue
            name = prefix + path.relative_to(base).as_posix()
            attachments[name] = {
                "content_type": CONTENT_TYPES[suffix],
                "data": base64.b64encode(path.read_bytes()).decode("ascii"),
            }
    return attachments


def main():
    env = load_env(ROOT / ".env")
    db_name = env.get("COUCHDB_DB", "schedule")
    couch = CouchDB(env["COUCHDB_URL"], env["COUCHDB_USER"], env["COUCHDB_PASSWORD"])

    attachments = collect()
    if "index.html" not in attachments:
        raise SystemExit("refusing to deploy: src/index.html not found")

    result = couch.put_doc(db_name, {"_id": DESIGN_ID, "_attachments": attachments})

    for name in sorted(attachments):
        print(f"  {name}")
    print(f"deployed {len(attachments)} files as {DESIGN_ID} rev {result['rev']}")
    print(f"open {env['COUCHDB_URL']}/{db_name}/{DESIGN_ID}/index.html")


if __name__ == "__main__":
    main()
