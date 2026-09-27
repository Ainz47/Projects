import json
import threading

import httpx
import pytest

from store import MemoryStore, SupabaseStore


# --- MemoryStore: the behaviour every store must have ---

def test_save_merges_fields_for_the_same_store_day():
    s = MemoryStore()
    s.save("Store_104", "2026-02-24", {"gross_sales": 5000.0})
    s.save("Store_104", "2026-02-24", {"labor_cost": 1500.0, "labor_hours": 75.0})
    row = s.get("Store_104", "2026-02-24")
    assert (row["gross_sales"], row["labor_cost"], row["labor_hours"]) == (5000.0, 1500.0, 75.0)
    assert len(s.rows) == 1


def test_get_missing_is_none():
    assert MemoryStore().get("Store_104", "2026-02-24") is None


def test_alert_can_be_claimed_once():
    s = MemoryStore()
    s.save("Store_104", "2026-02-24", {"gross_sales": 1.0})
    assert s.claim_alert("Store_104", "2026-02-24") is True
    assert s.claim_alert("Store_104", "2026-02-24") is False


def test_released_claim_can_be_taken_again():
    s = MemoryStore()
    s.save("Store_104", "2026-02-24", {"gross_sales": 1.0})
    s.claim_alert("Store_104", "2026-02-24")
    s.release_alert("Store_104", "2026-02-24")
    assert s.claim_alert("Store_104", "2026-02-24") is True


def test_concurrent_claims_have_one_winner():
    s = MemoryStore()
    s.save("Store_104", "2026-02-24", {"gross_sales": 1.0})
    wins = []
    threads = [threading.Thread(target=lambda: wins.append(s.claim_alert("Store_104", "2026-02-24"))) for _ in range(20)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert wins.count(True) == 1


# --- SupabaseStore: the PostgREST requests it makes ---

def _store(handler):
    client = httpx.Client(transport=httpx.MockTransport(handler))
    return SupabaseStore("https://proj.supabase.co", "service-key", client=client)


def test_save_is_a_native_upsert_on_store_and_date():
    seen = {}

    def handler(req):
        seen.update(method=req.method, url=req.url, prefer=req.headers["prefer"], body=json.loads(req.content),
                    apikey=req.headers["apikey"], auth=req.headers["authorization"])
        return httpx.Response(201, json=[])

    _store(handler).save("Store_104", "2026-02-24", {"gross_sales": 5000.0})
    assert seen["method"] == "POST"
    assert seen["url"].path == "/rest/v1/daily_metrics"
    assert seen["url"].params["on_conflict"] == "store_id,date"
    assert "resolution=merge-duplicates" in seen["prefer"]
    assert seen["body"] == {"store_id": "Store_104", "date": "2026-02-24", "gross_sales": 5000.0}
    assert (seen["apikey"], seen["auth"]) == ("service-key", "Bearer service-key")


def test_get_filters_on_both_keys():
    def handler(req):
        assert req.url.params["store_id"] == "eq.Store_104"
        assert req.url.params["date"] == "eq.2026-02-24"
        return httpx.Response(200, json=[{"store_id": "Store_104", "gross_sales": 5000}])

    assert _store(handler).get("Store_104", "2026-02-24")["gross_sales"] == 5000


def test_get_missing_row_is_none():
    assert _store(lambda req: httpx.Response(200, json=[])).get("Store_104", "2026-02-24") is None


@pytest.mark.parametrize("returned, claimed", [([{"id": 1}], True), ([], False)])
def test_claim_only_patches_an_unclaimed_row(returned, claimed):
    def handler(req):
        assert req.method == "PATCH"
        assert req.url.params["alert_sent_at"] == "is.null"
        assert json.loads(req.content)["alert_sent_at"]
        assert "return=representation" in req.headers["prefer"]
        return httpx.Response(200, json=returned)

    assert _store(handler).claim_alert("Store_104", "2026-02-24") is claimed


def test_release_clears_the_claim():
    def handler(req):
        assert req.method == "PATCH" and json.loads(req.content) == {"alert_sent_at": None}
        return httpx.Response(204)

    _store(handler).release_alert("Store_104", "2026-02-24")


def test_http_errors_are_raised_not_swallowed():
    with pytest.raises(httpx.HTTPStatusError):
        _store(lambda req: httpx.Response(401, json={"message": "Invalid API key"})).get("Store_104", "2026-02-24")


def test_from_env_is_none_without_settings(monkeypatch):
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_KEY", raising=False)
    assert SupabaseStore.from_env() is None
