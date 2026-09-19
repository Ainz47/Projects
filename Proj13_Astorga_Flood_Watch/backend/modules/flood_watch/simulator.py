import asyncio
import math
import time

from sqlmodel import Session, select

from core.database import engine
from .discord_alert import send_status_alert
from .ingestion import derive_status
from .models import ChokePoint, Reading

TICK_SECONDS = 15
# Sine-wave oscillation (not random walk) so seeded choke points behave
# predictably during a live demo instead of possibly flatlining or spamming
# alerts if left to pure randomness.
OSCILLATION_PERIOD_SECONDS = 180


async def run_simulator() -> None:
    start = time.monotonic()
    while True:
        await asyncio.sleep(TICK_SECONDS)
        elapsed = time.monotonic() - start
        with Session(engine) as session:
            simulated_points = session.exec(
                select(ChokePoint).where(ChokePoint.is_simulated == True)  # noqa: E712
            ).all()
            for idx, choke_point in enumerate(simulated_points):
                phase = idx * (math.pi / 2)  # stagger each point so they don't move in lockstep
                baseline = choke_point.watch_threshold_cm * 0.5
                amplitude = choke_point.critical_threshold_cm * 0.65
                water_level_cm = baseline + amplitude * math.sin(
                    (elapsed / OSCILLATION_PERIOD_SECONDS) * 2 * math.pi + phase
                )
                water_level_cm = max(water_level_cm, 0.0)
                distance_cm = choke_point.sensor_mount_height_cm - water_level_cm
                new_status = derive_status(choke_point, water_level_cm, distance_cm)

                reading = Reading(
                    choke_point_id=choke_point.id,
                    distance_cm=distance_cm,
                    water_level_cm=water_level_cm,
                    status=new_status,
                )
                session.add(reading)

                if new_status != choke_point.current_status:
                    choke_point.current_status = new_status
                    session.add(choke_point)
                    send_status_alert(choke_point.name, water_level_cm, new_status.value)

            session.commit()
