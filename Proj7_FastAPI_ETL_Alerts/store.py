"""Storage for one row per (store_id, date). MemoryStore for tests and local runs, SupabaseStore for Postgres."""
import os
import threading
from datetime import datetime, timezone

import httpx


class MemoryStore:
    def __init__(self):
        self.rows: dict[tuple[str, str], dict] = {}
        self._lock = threading.Lock()

    def save(self, store_id: str, day: str, fields: dict) -> None:
        with self._lock:
            row = self.rows.setdefault((store_id, day), {"store_id": store_id, "date": day, "alert_sent_at": None})
            row.update(fields)

    def get(self, store_id: str, day: str) -> dict | None:
        row = self.rows.get((store_id, day))
        return dict(row) if row else None

    def claim_alert(self, store_id: str, day: str) -> bool:
        with self._lock:
            row = self.rows.get((store_id, day))
            if not row or row["alert_sent_at"] is not None:
                return False
            row["alert_sent_at"] = datetime.now(timezone.utc).isoformat()
            return True

    def release_alert(self, store_id: str, day: str) -> None:
        with self._lock:
            if (store_id, day) in self.rows:
                self.rows[(store_id, day)]["alert_sent_at"] = None


class SupabaseStore:
    """Talks to Supabase's PostgREST API directly. Needs the service-role key (the table has RLS on, no policies)."""
    TABLE = "daily_metrics"

    def __init__(self, url: str, key: str, client: httpx.Client | None = None, timeout: float = 10.0):
        self.endpoint = f"{url.rstrip('/')}/rest/v1/{self.TABLE}"
        self.client = client or httpx.Client(timeout=timeout)
        self.headers = {"apikey": key, "Authorization": f"Bearer {key}"}

    @classmethod
    def from_env(cls) -> "SupabaseStore | None":
        url, key = os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY")
        return cls(url, key) if url and key else None

    def _send(self, method: str, params: dict, json=None, prefer: str | None = None) -> httpx.Response:
        headers = {**self.headers, **({"Prefer": prefer} if prefer else {})}
        r = self.client.request(method, self.endpoint, params=params, json=json, headers=headers)
        r.raise_for_status()
        return r

    @staticmethod
    def _key(store_id: str, day: str) -> dict:
        return {"store_id": f"eq.{store_id}", "date": f"eq.{day}"}

    def save(self, store_id: str, day: str, fields: dict) -> None:
        """INSERT ... ON CONFLICT (store_id, date) DO UPDATE, touching only the columns in `fields`."""
        self._send("POST", {"on_conflict": "store_id,date"}, json={"store_id": store_id, "date": day, **fields},
                   prefer="resolution=merge-duplicates,return=minimal")

    def get(self, store_id: str, day: str) -> dict | None:
        rows = self._send("GET", {**self._key(store_id, day), "select": "*"}).json()
        return rows[0] if rows else None

    def claim_alert(self, store_id: str, day: str) -> bool:
        """Sets alert_sent_at only where it is still null; exactly one concurrent caller gets the row back."""
        rows = self._send("PATCH", {**self._key(store_id, day), "alert_sent_at": "is.null"},
                          json={"alert_sent_at": datetime.now(timezone.utc).isoformat()},
                          prefer="return=representation").json()
        return len(rows) == 1

    def release_alert(self, store_id: str, day: str) -> None:
        self._send("PATCH", self._key(store_id, day), json={"alert_sent_at": None}, prefer="return=minimal")
