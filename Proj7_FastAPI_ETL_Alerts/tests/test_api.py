import httpx
import pytest
from fastapi.testclient import TestClient

from main import create_app, process_store_day
from store import MemoryStore

SECRET = "test-secret"
AUTH = {"X-Webhook-Secret": SECRET}
SALES = {"store_id": "Store_104", "date": "2026-02-24", "gross_sales": 5000.0}
LABOR = {"store_id": "Store_104", "date": "2026-02-24", "labor_hours": 75.0, "labor_cost": 1500.0}  # 30% labor


class Recorder:
    """Stands in for the Discord webhook; `ok` decides whether delivery succeeds."""
    def __init__(self, ok=True):
        self.ok, self.calls = ok, []

    def __call__(self, store_id, day, metrics):
        self.calls.append((store_id, day, metrics))
        return self.ok


@pytest.fixture
def setup():
    store, notify = MemoryStore(), Recorder()
    return store, notify, TestClient(create_app(store, notify, SECRET))


def test_both_halves_produce_metrics_and_one_alert(setup):
    store, notify, client = setup
    assert client.post("/webhook/sales", json=SALES, headers=AUTH).status_code == 202
    assert notify.calls == []  # labor hasn't arrived yet
    client.post("/webhook/labor", json=LABOR, headers=AUTH)
    row = store.get("Store_104", "2026-02-24")
    assert (row["cplh"], row["labor_pct"]) == (20.0, 30.0)
    assert notify.calls == [("Store_104", "2026-02-24", {"cplh": 20.0, "labor_pct": 30.0})]
    assert row["alert_sent_at"] is not None


def test_redelivered_webhook_does_not_alert_twice(setup):
    _, notify, client = setup
    for payload in (SALES, LABOR, LABOR, SALES):
        client.post(f"/webhook/{'sales' if 'gross_sales' in payload else 'labor'}", json=payload, headers=AUTH)
    assert len(notify.calls) == 1


def test_labor_first_works_too(setup):
    _, notify, client = setup
    client.post("/webhook/labor", json=LABOR, headers=AUTH)
    client.post("/webhook/sales", json=SALES, headers=AUTH)
    assert len(notify.calls) == 1


def test_below_threshold_saves_metrics_without_alert(setup):
    store, notify, client = setup
    client.post("/webhook/sales", json={**SALES, "gross_sales": 10000.0}, headers=AUTH)
    client.post("/webhook/labor", json=LABOR, headers=AUTH)
    assert store.get("Store_104", "2026-02-24")["labor_pct"] == 15.0
    assert notify.calls == []


def test_zero_sales_day_is_processed_not_skipped(setup):
    store, notify, client = setup
    client.post("/webhook/sales", json={**SALES, "gross_sales": 0}, headers=AUTH)
    client.post("/webhook/labor", json=LABOR, headers=AUTH)
    row = store.get("Store_104", "2026-02-24")
    assert (row["cplh"], row["labor_pct"]) == (20.0, None)
    assert notify.calls == []


def test_failed_alert_is_retried_by_the_next_webhook():
    store, notify = MemoryStore(), Recorder(ok=False)
    client = TestClient(create_app(store, notify, SECRET))
    client.post("/webhook/sales", json=SALES, headers=AUTH)
    client.post("/webhook/labor", json=LABOR, headers=AUTH)
    assert store.get("Store_104", "2026-02-24")["alert_sent_at"] is None
    notify.ok = True
    client.post("/webhook/labor", json=LABOR, headers=AUTH)
    assert len(notify.calls) == 2
    assert store.get("Store_104", "2026-02-24")["alert_sent_at"] is not None


def test_no_notifier_means_no_claim():
    store = MemoryStore()
    for payload, path in ((SALES, "sales"), (LABOR, "labor")):
        TestClient(create_app(store, None, SECRET)).post(f"/webhook/{path}", json=payload, headers=AUTH)
    assert store.get("Store_104", "2026-02-24")["alert_sent_at"] is None
    assert process_store_day(store, None, 25.0, "Store_104", "2026-02-24") == "over_threshold_no_notifier"


@pytest.mark.parametrize("headers, status", [({}, 401), ({"X-Webhook-Secret": "wrong"}, 401)])
def test_webhooks_need_the_secret(setup, headers, status):
    store, _, client = setup
    assert client.post("/webhook/sales", json=SALES, headers=headers).status_code == status
    assert store.rows == {}


def test_server_without_a_secret_refuses_everything():
    client = TestClient(create_app(MemoryStore(), None, None))
    assert client.post("/webhook/sales", json=SALES, headers={"X-Webhook-Secret": ""}).status_code == 503


@pytest.mark.parametrize("bad", [
    {**SALES, "gross_sales": -1},
    {**SALES, "date": "24/02/2026"},
    {**SALES, "store_id": "Store 104; drop"},
    {"store_id": "Store_104", "date": "2026-02-24"},
])
def test_invalid_payloads_are_rejected(setup, bad):
    store, _, client = setup
    assert client.post("/webhook/sales", json=bad, headers=AUTH).status_code == 422
    assert store.rows == {}


def test_storage_outage_returns_502_so_the_sender_retries():
    class Down(MemoryStore):
        def save(self, *a):
            raise httpx.ConnectError("unreachable")

    client = TestClient(create_app(Down(), None, SECRET))
    assert client.post("/webhook/sales", json=SALES, headers=AUTH).status_code == 502


def test_metrics_endpoint(setup):
    _, _, client = setup
    assert client.get("/metrics/Store_104/2026-02-24", headers=AUTH).status_code == 404
    client.post("/webhook/sales", json=SALES, headers=AUTH)
    assert client.get("/metrics/Store_104/2026-02-24", headers=AUTH).json()["gross_sales"] == 5000.0


def test_health_says_which_store_is_in_use(setup):
    assert setup[2].get("/health").json() == {"status": "ok", "store": "MemoryStore", "alerts": True}
