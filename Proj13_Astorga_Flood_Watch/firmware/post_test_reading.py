"""
Impersonate the ESP32 flood node -- POST a reading to the backend.

Use this to prove the API + dashboard pipeline works BEFORE wiring/flashing the
real device, and as a demo fallback to feed the live node (choke point 1) if the
hardware isn't connected during the pitch.

The payload is byte-for-byte what flood_sensor.ino sends:
    {"choke_point_id": <id>, "distance_cm": <cm>}

Examples:
    # single reading to the live node on this machine
    py firmware/post_test_reading.py --distance 30

    # point at the machine actually running FastAPI on the LAN
    py firmware/post_test_reading.py --base http://192.168.1.20:8000 --distance 30

    # stream a reading every 15 s (matches the firmware cadence) to keep the
    # live-node chart moving during a demo; Ctrl-C to stop
    py firmware/post_test_reading.py --loop --interval 15
"""
import argparse
import json
import sys
import time
import urllib.request

sys.stdout.reconfigure(encoding="utf-8")


def post_reading(base: str, cp_id: int, distance_cm: float) -> None:
    url = base.rstrip("/") + "/api/flood/readings"
    body = json.dumps({"choke_point_id": cp_id, "distance_cm": distance_cm}).encode()
    req = urllib.request.Request(
        url, data=body, headers={"Content-Type": "application/json"}, method="POST"
    )
    with urllib.request.urlopen(req, timeout=5) as resp:
        print(f"POST {resp.status} {resp.reason}: {resp.read().decode()[:200]}")


def main() -> None:
    ap = argparse.ArgumentParser(description="Simulate an ESP32 flood-node POST.")
    ap.add_argument("--base", default="http://127.0.0.1:8000",
                    help="Backend base URL (use the FastAPI machine's LAN IP for a real test)")
    ap.add_argument("--cp-id", type=int, default=1, help="Choke point id (live node = 1)")
    ap.add_argument("--distance", type=float, default=30.0,
                    help="Distance sensor->water in cm (smaller = higher water)")
    ap.add_argument("--loop", action="store_true", help="Keep posting on an interval")
    ap.add_argument("--interval", type=float, default=15.0, help="Seconds between posts in --loop")
    args = ap.parse_args()

    try:
        if args.loop:
            print(f"Streaming to {args.base} (cp {args.cp_id}) every {args.interval}s. Ctrl-C to stop.")
            while True:
                post_reading(args.base, args.cp_id, args.distance)
                time.sleep(args.interval)
        else:
            post_reading(args.base, args.cp_id, args.distance)
    except KeyboardInterrupt:
        print("\nStopped.")
    except Exception as e:
        print(f"FAILED: {e}")
        print("Checks: backend running? bound to 0.0.0.0 (not 127.0.0.1) for a LAN test? "
              "firewall allows the port? --base IP correct?")
        sys.exit(1)


if __name__ == "__main__":
    main()
