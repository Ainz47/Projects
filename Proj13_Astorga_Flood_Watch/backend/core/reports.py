from fastapi import APIRouter, Depends
from sqlmodel import Session, select

from .database import get_session
from .models import CitizenReport, ReportStatus

router = APIRouter(prefix="/api/reports", tags=["reports"])


@router.post("", response_model=CitizenReport)
def submit_report(report: CitizenReport, session: Session = Depends(get_session)):
    report.id = None
    report.status = ReportStatus.unverified
    session.add(report)
    session.commit()
    session.refresh(report)
    return report


@router.get("", response_model=list[CitizenReport])
def list_reports(service: str | None = None, session: Session = Depends(get_session)):
    query = select(CitizenReport)
    if service:
        query = query.where(CitizenReport.service == service)
    return session.exec(query).all()


@router.patch("/{report_id}/verify", response_model=CitizenReport)
def verify_report(report_id: int, session: Session = Depends(get_session)):
    report = session.get(CitizenReport, report_id)
    report.status = ReportStatus.verified
    session.add(report)
    session.commit()
    session.refresh(report)
    return report


@router.patch("/{report_id}/resolve", response_model=CitizenReport)
def resolve_report(report_id: int, session: Session = Depends(get_session)):
    report = session.get(CitizenReport, report_id)
    report.status = ReportStatus.resolved
    session.add(report)
    session.commit()
    session.refresh(report)
    return report
