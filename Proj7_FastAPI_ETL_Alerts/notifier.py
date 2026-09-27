"""Posts the high-labor alert to a Discord (or Slack-compatible) webhook."""
import httpx


def format_alert(store_id: str, day: str, metrics: dict) -> str:
    cplh = f"${metrics['cplh']:.2f}" if metrics["cplh"] is not None else "n/a"
    return (
        f"🚨 **High labor cost: {store_id}**\n"
        f"📅 {day}\n"
        f"📈 Labor: {metrics['labor_pct']:.2f}% of sales\n"
        f"🕒 Cost per labor hour: {cplh}\n"
        f"Review the schedule for this day."
    )


def send_labor_alert(webhook_url: str, store_id: str, day: str, metrics: dict,
                     client: httpx.Client | None = None, timeout: float = 10.0) -> bool:
    """True if the webhook accepted the message. Never raises: a failed alert must not fail the batch."""
    try:
        r = (client or httpx.Client(timeout=timeout)).post(webhook_url, json={"content": format_alert(store_id, day, metrics)})
        if r.is_success:
            return True
        print(f"Alert for {store_id} {day} rejected: HTTP {r.status_code}")
    except httpx.HTTPError as e:
        print(f"Alert for {store_id} {day} failed: {type(e).__name__}")
    return False
