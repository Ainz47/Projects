# Budget — Astorga Central: Flood Watch

All figures in Philippine pesos (₱). Prices are typical Philippine retail / online
marketplace ranges as of mid-2026; confirm against a current supplier quote before
citing exact numbers in the pitch.

## 1. Demo / prototype cost (what we actually spent to build the working demo)

| Item | Qty | Unit | Subtotal | Notes |
|---|---|---|---|---|
| ESP32 dev board | 1 | ₱180–250 | ₱180–250 | Already owned |
| JSN-SR04T waterproof ultrasonic sensor | 1 | ₱280–320 | ₱280–320 | To order |
| Jumper wires + resistors (voltage divider) | — | ₱30–50 | ₱30–50 | For the 5V→3.3V echo divider |
| **Demo total** | | | **≈ ₱300–350** | One live node; other 3 points simulated in software |

The demo runs on one real sensor node plus three software-simulated choke points,
so the *whole barangay picture* is shown for the price of a single sensor.

## 2. Production cost — per monitoring node (permanent field install)

| Item | Unit | Notes |
|---|---|---|
| ESP32 board | ₱180–250 | |
| JSN-SR04T ultrasonic sensor | ₱280–320 | ~20 cm blind zone → mount high |
| Solar panel (5–10W) + charge controller | ₱350–650 | Off-grid canal locations |
| 18650 Li-ion battery + holder | ₱150–300 | Overnight / no-sun operation |
| Waterproof enclosure (IP65) + mounting | ₱150–300 | Canal/bridge exposure |
| SIM / connectivity module (optional) | ₱0–500 | If no barangay Wi-Fi in range |
| **Per-node total** | **≈ ₱1,150–1,950** | Deploy at the 3–5 real choke points |

A 3-node rollout of the true flood chokepoints: **≈ ₱3,450–5,850** one-time.

## 3. Hosting / running cost

| Item | Monthly | Notes |
|---|---|---|
| Shared VPS (backend + SQLite + dashboard) | ₱200–500 | 1 small droplet serves the whole barangay |
| Discord alert channel | ₱0 | Webhook is free — the live alert channel |
| Map tiles (OpenStreetMap / CARTO) | ₱0 | No paid map API |
| SMS gateway (optional, production only) | usage-based | Paper/production channel; **not** wired in the demo to avoid cost |

**Running cost: ≈ ₱200–500 / month** for the entire barangay deployment.

## 4. Why this is affordable for a barangay

- No paid map API, no cloud lock-in — OpenStreetMap + a single cheap VPS.
- One sensor proves the concept; the platform (`core/`) is reused for future
  services (potholes, waste, health) at zero extra infrastructure cost.
- Alerts ride a free Discord channel for the demo; SMS is a documented upgrade,
  not a dependency.
