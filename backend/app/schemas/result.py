import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ResultOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    job_id: uuid.UUID
    status: str
    output_path: str | None
    psnr: float | None
    ssim: float | None
    lpips: float | None
    processing_time: float | None
    output_width: int | None
    output_height: int | None
    created_at: datetime
    is_mock: bool = Field(
        default=True,
        description="Always true until Phase 6/7 wire up the real model and evaluation.",
    )
