import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


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
    # Phase 6: real, DB-backed — True for MockProcessor results, False for
    # SuperResolutionProcessor results. No longer a hardcoded default.
    is_mock: bool
    model_name: str | None
    model_version: str | None
    device: str | None
    # False whenever psnr/ssim/lpips are null because there was no
    # ground-truth HR image to compare against (the normal case for real
    # inference) — never invented in that case. See ai/metrics/image_metrics.py.
    metrics_available: bool
