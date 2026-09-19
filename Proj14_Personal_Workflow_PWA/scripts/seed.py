"""Create the schedule database and write the reference documents.

Safe to re-run. The template merges on every run: checks and tasks are the
two collections the app edits in place (retiring a check, adding a task,
migrating a dedicated task id), so those come from CouchDB, and any id that
only exists in the local file is added on top. Everything else in the
template - streaks, days, wake/sleep, attributes, and so on - is structural
and only ever changes by hand-editing the file, so it always comes from the
file. Pass --force to overwrite checks and tasks from the file too, discarding
whatever the app has written since the last seed.

The campaign document is still written every time: nothing in the app edits it.
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from couch import CouchDB, load_env  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "src" / "data"

TEMPLATE_FILE = "schedule-template.json"
CAMPAIGN_FILE = "campaign-talk-demo.json"

TEMPLATE_ID = "schedule:v1"

# The collections the app writes into at runtime (see template-edit.js):
# retireCheck/addCheck touch checks (and tasks/streaks for a new check's own
# task), addTask touches tasks. Merged rather than overwritten so a seed run
# never discards an in-app edit.
APP_OWNED_KEYS = ("checks", "tasks")


def merge_template(remote, local):
    """Combine the local file with the live doc for the app-owned keys.

    The file wins for everything except APP_OWNED_KEYS, where the live
    document wins per id and only ids missing from the live document (new
    ones added by hand in the file) are carried over.
    """
    if remote is None:
        return local

    merged = dict(local)
    for key in APP_OWNED_KEYS:
        entries = dict(remote.get(key, {}))
        for entry_id, entry in local.get(key, {}).items():
            entries.setdefault(entry_id, entry)
        merged[key] = entries
    return merged


def seed_docs(couch, db_name, data_dir, force=False):
    """Write the reference documents, returning (doc_id, action) pairs."""
    results = []
    for filename in (TEMPLATE_FILE, CAMPAIGN_FILE):
        doc = json.loads((Path(data_dir) / filename).read_text(encoding="utf-8"))
        doc_id = doc["_id"]

        if doc_id == TEMPLATE_ID and not force:
            existing = couch.get_doc(db_name, doc_id)
            doc = merge_template(existing, doc)

        couch.put_doc(db_name, doc)
        results.append((doc_id, "wrote"))
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--force", action="store_true",
        help="overwrite schedule:v1's checks and tasks from the file too, "
             "discarding in-app edits made since the last seed",
    )
    args = parser.parse_args()

    env = load_env(ROOT / ".env")
    db_name = env.get("COUCHDB_DB", "schedule")
    couch = CouchDB(env["COUCHDB_URL"], env["COUCHDB_USER"], env["COUCHDB_PASSWORD"])

    created = couch.ensure_db(db_name)
    print(f"database {db_name}: {'created' if created else 'already present'}")

    for doc_id, _action in seed_docs(couch, db_name, DATA, force=args.force):
        print(f"wrote {doc_id}")

    print("seed complete")


if __name__ == "__main__":
    main()
