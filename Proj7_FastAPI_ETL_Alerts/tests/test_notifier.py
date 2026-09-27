import json

import httpx

from notifier import format_alert, send_labor_alert

METRICS = {"cplh": 20.0, "labor_pct": 30.0}


def _client(handler):
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_message_has_the_store_day_and_numbers():
    text = format_alert("Store_104", "2026-02-24", METRICS)
    assert "Store_104" in text and "2026-02-24" in text and "30.00%" in text and "$20.00" in text


def test_undefined_cplh_reads_na():
    assert "n/a" in format_alert("Store_104", "2026-02-24", {"cplh": None, "labor_pct": 40.0})


def test_delivered_is_true_and_posts_discord_content():
    sent = {}

    def handler(req):
        sent.update(json.loads(req.content))
        return httpx.Response(204)

    assert send_labor_alert("https://discord.test/hook", "Store_104", "2026-02-24", METRICS, client=_client(handler))
    assert "Store_104" in sent["content"]


def test_rejected_is_false():
    assert not send_labor_alert("https://discord.test/hook", "S", "2026-02-24", METRICS,
                                client=_client(lambda req: httpx.Response(429)))


def test_network_error_is_false_not_raised():
    def handler(req):
        raise httpx.ConnectTimeout("slow")

    assert not send_labor_alert("https://discord.test/hook", "S", "2026-02-24", METRICS, client=_client(handler))
