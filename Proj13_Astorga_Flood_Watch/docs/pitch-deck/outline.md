# Pitch Deck — Astorga Central: Flood Watch

SK Barangay Astorga "Project Pitching". Deck flow and scoring below are copied
from the official mechanics (Mechanics/*.jpg).

- **Deadline:** July 29, 2026, 11:59 PM
- **Center of Participation addressed:** Environment (also touches Active
  Citizenship and Governance via citizen reporting + official response).
- **Eligibility check:** entry must be *original, tangible, and functional* — not
  a concept, outreach, or advocacy activity. Our working prototype (1 live ESP32
  ultrasonic node + live dashboard + citizen report form) meets this. Keep the
  physical node on the table during the pitch; that is the graded artifact.

## Scoring — write every slide to earn these

| Criterion | Weight | What wins it | Where we prove it |
|---|---|---|---|
| Practicality & Feasibility | **30%** | Real-world usefulness + it can actually be deployed | Slide 5 (working demo), Slide 6 (₱300 demo / ₱200–500/mo run) |
| Innovation & Creativity | **25%** | Originality of the idea | Slide 4 (platform, not single app) + fail-safe blind-zone logic |
| Functionality & Prototype Quality | **25%** | Quality/performance of the actual prototype | Slide 5 (live sensor → alert → map, on stage) |
| Presentation & Communication | **20%** | Clear, confident delivery | Whole deck + rehearsed live demo |

Practicality is the heaviest slice (30%) — lean the demo and budget slides hard
on "this is cheap and it works today."

---

## 1. Project Title
- **Astorga Central — Flood Watch**: a low-cost flood early-warning system for
  Barangay Astorga.
- One-line tagline: *"Know the water is rising before it reaches the door."*
- Team name / members (KK of Barangay Astorga).

## 2. Project Background
- Barangay Astorga, Santa Cruz, Davao del Sur (pop. ~12,263).
- Situated near creek/canal drainage lines that overflow in heavy monsoon rain.
- Reference the real OCD-Davao flood incident as the judge-verifiable hook (cite
  date/source on the slide).
- Today: no early warning — residents find out when water is already in the street.

## 3. The Problem
- Flash flooding at known choke points (canal crossings, culverts, low roads).
- Warnings today are word-of-mouth and too late to move people/property.
- No data: the barangay cannot see which points are rising in real time.
- Frame it as a repeating, specific, local problem — not a general "floods are bad."

## 4. The Solution / Intervention
- **Astorga Central**: a barangay platform whose first module is **Flood Watch**.
- Ultrasonic sensors at choke points measure water level and auto-classify
  Normal / Watch / Critical; status changes fire an instant alert.
- Citizens report flooding from their phone (GPS + pinned location); officials
  verify and resolve on a live map.
- **Innovation angle:** it is a *reusable civic platform*, not a one-off gadget —
  the same core runs future services (potholes, waste, health) at no new cost.
  Plus a fail-safe design: a sensor blind-zone reading is treated as Critical, so
  it never stays silent when it matters.

## 5. Action Plan / Prototype  ← the 25% functionality + demo moment
- **Live demo, in this order:**
  1. Show the dashboard: 4 choke points on the map, live status colors.
  2. Pour/raise water at the real ESP32 node (or trigger it) → status flips to
     Critical → the top status ribbon turns red → Discord alert pops.
  3. Submit a citizen report from a phone → it appears on the officials' map.
  4. Officials verify → resolve.
- Rollout plan: pilot the 1 live node now; scale to the 3–5 true choke points.
- Tech (say it plainly): ESP32 + waterproof ultrasonic sensor, free OpenStreetMap,
  free Discord alerts, one small server.

## 6. Budget Plan
- Pull the numbers from `docs/budget.md`:
  - Demo cost: **≈ ₱300–350** (one node; three points simulated).
  - Production: **≈ ₱1,150–1,950 per node**; 3-node rollout ₱3,450–5,850 one-time.
  - Running: **≈ ₱200–500 / month** for the whole barangay.
- Message: cheap to prove, cheap to run, no paid map/cloud lock-in.

## 7. Target Beneficiaries
- Primary: ~12,263 residents of Barangay Astorga, especially households near the
  creek/canal choke points.
- Barangay Disaster Risk Reduction & Management Committee (faster decisions).
- Secondary/future: any barangay that adopts the platform; future non-flood
  services reuse the same system.

---

## Delivery notes (Presentation — 20%)
- Rehearse the demo until the water-rising → red-ribbon → alert sequence is
  smooth; a working live demo is the single most persuasive thing on stage.
- Have a backup: short screen recording of the demo in case venue Wi-Fi fails
  (map tiles and alerts need internet).
- Keep the physical sensor node visible the whole time — it is the tangible
  artifact the mechanics require.
