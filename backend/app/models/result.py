import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.core.types import GUID


class Result(Base):
    __tablename__ = "results"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)

    job_id: Mapped[uuid.UUID] = mapped_column(
        GUID(),
        ForeignKey("processing_jobs.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )

    output_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)

    # MOCK/TEMPORARY — randomized within plausible ranges by MockProcessor.
    # Replaced by real evaluation against ground truth in Phase 7.
    psnr: Mapped[float | None] = mapped_column(Float, nullable=True)
    ssim: Mapped[float | None] = mapped_column(Float, nullable=True)
    lpips: Mapped[float | None] = mapped_column(Float, nullable=True)

    processing_time: Mapped[float | None] = mapped_column(Float, nullable=True)
    output_width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    output_height: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Phase 6: which processor actually produced this result. Real for
    # MockProcessor (is_mock=True) and for SuperResolutionProcessor
    # (is_mock=False) alike — this column is what makes that distinction a
    # fact read from the database rather than a hardcoded API default.
    is_mock: Mapped[bool] = mapped_column(nullable=False, default=True)
    model_name: Mapped[str | None] = mapped_column(String(64), nullable=True)
    model_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    device: Mapped[str | None] = mapped_column(String(16), nullable=True)
    # False whenever there is no ground-truth HR image to compare against
    # (the normal case for real-world inference) — psnr/ssim/lpips stay
    # null rather than ever being invented. See ai/metrics/image_metrics.py.
    metrics_available: Mapped[bool] = mapped_column(nullable=False, default=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    job: Mapped["ProcessingJob"] = relationship(back_populates="result")  # noqa: F821
