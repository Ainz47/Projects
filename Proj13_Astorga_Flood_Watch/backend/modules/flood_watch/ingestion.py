from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session

from core.database import get_session
from .discord_alert import send_status_alert
from .models import ChokePoint, FloodStatus, Reading

router = APIRouter(prefix="/api/flood", tags=["flood_watch"])

# JSN-SR04T cannot reliably read closer than ~20cm (blind zone). Treat anything
# under this as "water is at/past the sensor" rather than trusting a bad echo --
# fail-safe toward alerting rather than silently dropping the reading.
MIN_RELIABLE_DISTANCE_CM = 20.0


class ReadingIn(BaseModel):
    choke_point_id: int
    distance_cm: float


def derive_status(choke_point: ChokePoint, water_level_cm: float, distance_cm: float) -> FloodStatus:
    if distance_cm < MIN_RELIABLE_DISTANCE_CM:
        return FloodStatus.critical
    if water_level_cm >= choke_point.critical_threshold_cm:
        return FloodStatus.critical
    if water_level_cm >= choke_point.watch_threshold_cm:
        return FloodStatus.watch
    return FloodStatus.normal


@router.post("/readings", response_model=Reading)
def ingest_reading(payload: ReadingIn, session: Session = Depends(get_session)):
    choke_point = session.get(ChokePoint, payload.choke_point_id)
    if choke_point is None:
        raise HTTPException(status_code=404, detail="Unknown choke point")

    water_level_cm = choke_point.sensor_mount_height_cm - payload.distance_cm
    new_status = derive_status(choke_point, water_level_cm, payload.distance_cm)

    reading = Reading(
        choke_point_id=choke_point.id,
        distance_cm=payload.distance_cm,
        water_level_cm=water_level_cm,
        status=new_status,
    )
    session.add(reading)

    previous_status = choke_point.current_status
    if new_status != previous_status:
        choke_point.current_status = new_status
        session.add(choke_point)
        if new_status in (FloodStatus.watch, FloodStatus.critical):
            send_status_alert(choke_point.name, water_level_cm, new_status.value)

    session.commit()
    session.refresh(reading)
    return reading
