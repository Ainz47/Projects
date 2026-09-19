from fastapi import APIRouter, Depends
from sqlmodel import Session, select

from .database import get_session
from .models import CitizenReport

router = APIRouter(prefix="/api/map", tags=["map"])


@router.get("")
def get_map_pins(session: Session = Depends(get_session)):
    # Aggregates pins across modules. Importing flood_watch here (rather than the
    # reverse) keeps flood_watch itself free of any core-layer dependency --
    # adding a second module later means adding one more import + block here.
    from modules.flood_watch.models import ChokePoint

    pins = []

    for cp in session.exec(select(ChokePoint)).all():
        pins.append(
            {
                "id": f"choke_point:{cp.id}",
                "type": "choke_point",
                "lat": cp.lat,
                "lng": cp.lng,
                "status": cp.current_status,
                "label": cp.name,
                "is_simulated": cp.is_simulated,
            }
        )

    for report in session.exec(select(CitizenReport)).all():
        pins.append(
            {
                "id": f"report:{report.id}",
                "type": "report",
                "lat": report.lat,
                "lng": report.lng,
                "status": report.status,
                "label": report.description,
                "request_monitoring": report.request_monitoring,
            }
        )

    return pins
