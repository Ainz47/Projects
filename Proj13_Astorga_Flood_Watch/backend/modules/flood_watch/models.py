from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from sqlmodel import SQLModel, Field


class FloodStatus(str, Enum):
    normal = "normal"
    watch = "watch"
    critical = "critical"


class ChokePoint(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    lat: float
    lng: float
    sensor_mount_height_cm: float  # distance from sensor to dry canal/road floor
    watch_threshold_cm: float  # water_level_cm at which status becomes "watch"
    critical_threshold_cm: float  # water_level_cm at which status becomes "critical"
    is_simulated: bool = Field(default=False)
    current_status: FloodStatus = Field(default=FloodStatus.normal)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class Reading(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    choke_point_id: int = Field(foreign_key="chokepoint.id", index=True)
    distance_cm: float  # raw sensor reading (sensor to water surface)
    water_level_cm: float  # sensor_mount_height_cm - distance_cm
    status: FloodStatus
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
