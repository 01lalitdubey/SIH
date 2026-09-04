import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class AOIBounds(BaseModel):
    north: float
    south: float
    east: float
    west: float


class ProcessingCreateRequest(BaseModel):
    image_id: uuid.UUID | None = None
    analysis_name: str = Field(min_length=1, max_length=255)
    scale_factor: Literal[2, 4]
    aoi: AOIBounds | None = None
    # Demo-only: lets the frontend's "Simulate failure" button exercise a
    # real failure path through the mock pipeline. Never set by real jobs.
    simulate_failure: bool = False

    @model_validator(mode="after")
    def require_a_source(self) -> "ProcessingCreateRequest":
        if self.image_id is None and self.aoi is None:
            raise ValueError("Either image_id or aoi must be provided")
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
