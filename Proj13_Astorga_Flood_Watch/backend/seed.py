"""Seed the demo choke points for Barangay Astorga.

Run once after init_db (or any time -- it is idempotent, keyed on choke-point
name). Creates one REAL node (is_simulated=False; this is the physical ESP32 +
JSN-SR04T that reports live via POST /api/flood/readings) plus three SIMULATED
nodes the background simulator oscillates so the dashboard shows a live,
multi-point picture during the pitch.

Coordinates are anchored to real OpenStreetMap-tagged landmarks in Barangay
Astorga, Santa Cruz, Davao del Sur (barangay center ~6.9116 N, 125.4611 E,
elev ~18 m). Astorga is a coastal barangay on Davao Gulf; its floods come from
the Sibulan / Baroring / Baracatan river systems draining east to the sea, so
the choke-point line runs roughly north->south along the built-up strip toward
the Mangga Beach outfall.

These are landmark-derived estimates (school, barangay hall, high school,
beach), NOT surveyed canal choke points -- replace with real GPS fixes from a
site visit before the actual field deployment. They are accurate enough that
the demo map drops pins on the real barangay.

    cd backend && py seed.py       # or: venv/Scripts/python seed.py
"""

from sqlmodel import Session, select

from core.database import engine, init_db
from modules.flood_watch.models import ChokePoint

# name -> (lat, lng, mount_height_cm, watch_cm, critical_cm, is_simulated)
# Anchors: Barangay Hall 6.9146/125.4582, Federico Yap NHS 6.9026/125.4570,
# Astorga Central ES 6.8996/125.4582, Mangga Beach 6.8976/125.4592.
CHOKE_POINTS = {
    "Astorga Main Canal (Barangay Hall Bridge)": (6.9142, 125.4576, 120.0, 40.0, 75.0, False),
    "Federico Yap NHS Creek Crossing": (6.9026, 125.4573, 100.0, 30.0, 60.0, True),
    "Astorga Central ES Culvert": (6.8996, 125.4581, 90.0, 25.0, 55.0, True),
    "Mangga Beach Road Low Point": (6.8978, 125.4589, 110.0, 35.0, 70.0, True),
}


def seed() -> None:
    init_db()
    created, skipped = 0, 0
    with Session(engine) as session:
        for name, (lat, lng, mount, watch, critical, simulated) in CHOKE_POINTS.items():
            exists = session.exec(
                select(ChokePoint).where(ChokePoint.name == name)
            ).first()
            if exists:
                skipped += 1
                continue
            session.add(
                ChokePoint(
                    name=name,
                    lat=lat,
                    lng=lng,
                    sensor_mount_height_cm=mount,
                    watch_threshold_cm=watch,
                    critical_threshold_cm=critical,
                    is_simulated=simulated,
                )
            )
            created += 1
        session.commit()
    print(f"Seed complete: {created} created, {skipped} already existed.")


if __name__ == "__main__":
    seed()
