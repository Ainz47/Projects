"""
history.py — Saves and loads deployment records to deployments.json.
"""
import json
import uuid
import os
from datetime import datetime

HISTORY_FILE = os.path.join(os.path.dirname(__file__), "..", "deployments.json")


def _load() -> list:
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                records = json.load(f)
            # Older versions persisted wp_password. Drop it on read so history
            # written before this change stops being served, and is rewritten
            # without it on the next save.
            for r in records:
                r.pop("wp_password", None)
            return records
        except Exception:
            pass
    return []


def _save(records: list):
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(records, f, indent=2, ensure_ascii=False)


def save_deployment(cfg_dict: dict, published: list, failed: list) -> str:
    records = _load()
    failed_count = len(failed)
    if not published and not failed:
        status = "failed"
    elif not failed_count:
        status = "complete"
    else:
        status = "partial" if published else "failed"
    record = {
        "id": str(uuid.uuid4()),
        "saved_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "business_name": cfg_dict.get("business_name", ""),
        "city": cfg_dict.get("city", ""),
        "state": cfg_dict.get("state", ""),
        "wp_url": cfg_dict.get("wp_url", ""),
        "wp_username": cfg_dict.get("wp_username", ""),
        "phone": cfg_dict.get("phone", ""),
        "primary_color": cfg_dict.get("primary_color", "#ff5e14"),
        "dark_color": cfg_dict.get("dark_color", "#1a1a1a"),
        "services": cfg_dict.get("services", []),
        "blog_topics": cfg_dict.get("blog_topics", []),
        "maps_embed_url": cfg_dict.get("maps_embed_url", ""),
        "published_urls": published,
        "failed": failed,
        "status": status,
    }
    records.insert(0, record)
    _save(records)
    return record["id"]


def update_deployment(record_id: str, published: list, failed: list, retried_labels: set = None):
    """
    Update a deployment record after a retry run.
    retried_labels: set of labels that were attempted in this retry.
      If provided, only those labels are replaced in the failed list.
      Labels NOT in retried_labels are preserved as still-failed.
    """
    records = _load()
    for r in records:
        if r["id"] == record_id:
            # Merge newly published URLs (avoid duplicates)
            existing_urls = {u["url"] for u in r.get("published_urls", [])}
            for item in published:
                if item["url"] not in existing_urls:
                    r["published_urls"].append(item)

            if retried_labels is not None:
                # Keep original failures that were NOT part of this retry
                untouched = [
                    f for f in r.get("failed", [])
                    if (f["label"] if isinstance(f, dict) else f) not in retried_labels
                ]
                r["failed"] = untouched + list(failed)
            else:
                r["failed"] = list(failed)

            has_published = bool(r.get("published_urls"))
            has_failed = bool(r.get("failed"))
            if not has_published and not has_failed:
                r["status"] = "failed"
            elif not has_failed:
                r["status"] = "complete"
            else:
                r["status"] = "partial" if has_published else "failed"
            r["saved_at"] = datetime.now().strftime("%Y-%m-%d %H:%M")
            break
    _save(records)


def list_deployments() -> list:
    return _load()


def get_deployment(record_id: str) -> dict | None:
    for r in _load():
        if r["id"] == record_id:
            return r
    return None


def delete_deployment(record_id: str):
    records = [r for r in _load() if r["id"] != record_id]
    _save(records)
