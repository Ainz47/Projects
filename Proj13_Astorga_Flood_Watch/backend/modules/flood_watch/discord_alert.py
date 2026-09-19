import os
import threading

import httpx

DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL", "")


def _deliver(message: str) -> None:
    # Runs off the event loop: the simulator calls send_status_alert from inside
    # an async coroutine, so a slow or dead network here would otherwise stall
    # every request for the length of the timeout.
    try:
        httpx.post(DISCORD_WEBHOOK_URL, json={"content": message}, timeout=5.0)
    except Exception as exc:
        print(f"[discord] alert not delivered: {exc}")


def send_status_alert(choke_point_name: str, water_level_cm: float, status: str) -> None:
    if not DISCORD_WEBHOOK_URL:
        return  # no webhook configured yet -- fail silently during early dev, not during demo
    message = (
        f"**Astorga Central - Flood Watch**\n"
        f"Choke point **{choke_point_name}** is now **{status.upper()}** "
        f"(water level: {water_level_cm:.1f} cm)"
    )
    threading.Thread(target=_deliver, args=(message,), daemon=True).start()
