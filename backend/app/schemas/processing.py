import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.satellite import SatelliteSceneOut


class AOIBounds(BaseModel):
    north: float = Field(ge=-90, le=90)
    south: float = Field(ge=-90, le=90)
    east: float = Field(ge=-180, le=180)
    west: float = Field(ge=-180, le=180)

    @model_validator(mode="after")
    def bounds_are_a_real_box(self) -> "AOIBounds":
        if self.north <= self.south:
            raise ValueError("AOI 'north' must be greater than 'south'.")
        if self.east <= self.west:
            raise ValueError("AOI 'east' must be greater than 'west'.")
        return self


class ProcessingCreateRequest(BaseModel):
    image_id: uuid.UUID | None = None
    analysis_name: str = Field(min_length=1, max_length=255)
    scale_factor: Literal[2, 4]
    aoi: AOIBounds | None = None

    # Phase 5: optional Sentinel-2 search parameters, only meaningful when
    # `aoi` is set. The existing frontend map doesn't expose controls for
    # these yet, so all three are optional — SatelliteService applies
    # documented defaults (last 30 days, max_cloud_cover=20%) when omitted,
    # exactly as this schema's example shows.
    start_date: date | None = None
    end_date: date | None = None
    max_cloud_cover: float | None = Field(default=None, ge=0, le=100)

    # Demo-only: lets the frontend's "Simulate failure" button exercise a
    # real failure path through the mock pipeline. Never set by real jobs.
    simulate_failure: bool = False

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "aoi": {"north": 25.7, "south": 20.6, "east": 81.6, "west": 72.4},
                "analysis_name": "Coastal Delta — Sundarbans",
                "scale_factor": 4,
                "start_date": "2026-08-01",
                "end_date": "2026-09-01",
                "max_cloud_cover": 20,
            }
        }
    )

    @model_validator(mode="after")
    def require_a_source(self) -> "ProcessingCreateRequest":
        if self.image_id is None and self.aoi is None:
            raise ValueError("Either image_id or aoi must be provided")
        return self

    @model_validator(mode="after")
    def date_range_is_ordered(self) -> "ProcessingCreateRequest":
        if self.start_date and self.end_date and self.start_date >= self.end_date:
            raise ValueError("start_date must be earlier than end_date")
        return self


class ProcessingJobOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID = Field(serialization_alias="job_id")
    image_id: uuid.UUID | None
    analysis_name: str
    scale_factor: int
    status: str
    progress: int
    current_stage: str | None
    error_message: str | None
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None
    # Phase 5: present only for AOI-driven jobs once a scene has been
    # identified (may exist even if the job later failed at download).
    satellite_scene: SatelliteSceneOut | None = None
