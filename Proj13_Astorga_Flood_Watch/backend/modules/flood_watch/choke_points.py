from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from core.database import get_session
from .models import ChokePoint, Reading

router = APIRouter(prefix="/api/flood/choke-points", tags=["flood_watch"])


@router.post("", response_model=ChokePoint)
def create_choke_point(choke_point: ChokePoint, session: Session = Depends(get_session)):
    choke_point.id = None
    session.add(choke_point)
    session.commit()
    session.refresh(choke_point)
    return choke_point


@router.get("", response_model=list[ChokePoint])
def list_choke_points(session: Session = Depends(get_session)):
    return session.exec(select(ChokePoint)).all()


@router.get("/{choke_point_id}/history", response_model=list[Reading])
def choke_point_history(choke_point_id: int, limit: int = 200, session: Session = Depends(get_session)):
    if session.get(ChokePoint, choke_point_id) is None:
        raise HTTPException(status_code=404, detail="Unknown choke point")
    query = (
        select(Reading)
        .where(Reading.choke_point_id == choke_point_id)
        .order_by(Reading.timestamp.desc())
        .limit(limit)
    )
    return list(reversed(session.exec(query).all()))
