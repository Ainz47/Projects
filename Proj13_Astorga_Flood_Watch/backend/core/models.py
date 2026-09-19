from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from sqlmodel import SQLModel, Field


class ReportStatus(str, Enum):
    unverified = "unverified"
    verified = "verified"
    resolved = "resolved"


class CitizenReport(SQLModel, table=True):
    """Generic 'report something at a location' submission -- the platform-core
    primitive that any future barangay service (potholes, waste, health) reuses."""

    id: Optional[int] = Field(default=None, primary_key=True)
    service: str = Field(default="flood_watch", index=True)  # which module this report belongs to
    description: str
    photo_url: Optional[str] = None
    lat: float
    lng: float
    request_monitoring: bool = Field(default=False)
    status: ReportStatus = Field(default=ReportStatus.unverified)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
