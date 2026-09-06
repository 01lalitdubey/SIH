import uuid
from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.core.types import GUID


class JobStatus:
    """Plain string constants (not a DB-level enum) so new stages/statuses
    don't require a migration — validated at the API/service layer instead."""

    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class ProcessingStage:
    PREPROCESSING = "preprocessing"
    FEATURE_EXTRACTION = "feature_extraction"
    SUPER_RESOLUTION = "super_resolution"
    POST_PROCESSING = "post_processing"
    EVALUATION = "evaluation"

    ORDERED = [
        PREPROCESSING,
        FEATURE_EXTRACTION,
        SUPER_RESOLUTION,
        POST_PROCESSING,
        EVALUATION,
    ]


class ProcessingJob(Base):
    __tablename__ = "processing_jobs"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)

    image_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("images.id", ondelete="SET NULL"), nullable=True
    )

    analysis_name: Mapped[str] = mapped_column(String(255), nullable=False)
    scale_factor: Mapped[int] = mapped_column(Integer, nullable=False)

    # AOI bounds ({north, south, east, west}) when the job is AOI-driven
    # rather than (or in addition to) an uploaded image. Satellite-backed
    # AOI search/fetch is a Phase 5 concern — this just stores what the
    # frontend's map already collects.
    aoi_geometry: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    status: Mapped[str] = mapped_column(String(32), nullable=False, default=JobStatus.QUEUED)
    progress: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    current_stage: Mapped[str | None] = mapped_column(String(64), nullable=True)

    # Demo-only control flag so the frontend's "Simulate failure" action has
    # something real to trigger server-side. Not a real failure condition.
    simulate_failure: Mapped[bool] = mapped_column(default=False, nullable=False)

    error_message: Mapped[str | None] = mapped_column(String(1024), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    image: Mapped["Image | None"] = relationship(back_populates="processing_jobs")  # noqa: F821
    result: Mapped["Result | None"] = relationship(  # noqa: F821
        back_populates="job", cascade="all, delete-orphan", uselist=False
    )
    # Phase 5: present only for AOI-driven jobs where a real Sentinel-2 scene
    # was identified (and possibly retrieved) via SatelliteService.
    satellite_scene: Mapped["SatelliteScene | None"] = relationship(  # noqa: F821
        back_populates="processing_job", cascade="all, delete-orphan", uselist=False
    )
