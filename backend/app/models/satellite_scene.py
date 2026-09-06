import uuid
from datetime import datetime

from sqlalchemy import JSON, BigInteger, DateTime, Float, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.core.types import GUID


class DownloadStatus:
    """Plain string constants (not a DB-level enum), matching the convention
    already used by JobStatus/ProcessingStage in models/processing_job.py."""

    PENDING = "pending"
    DOWNLOADING = "downloading"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"  # scene identified but not retrieved (e.g. over the size cap)


class SatelliteScene(Base):
    """A single satellite product selected for one ProcessingJob's AOI.

    One row per job (not per candidate) — search results are kept only in
    memory during selection; only the scene that was actually chosen (and,
    on a download failure, still identified) is persisted here. This is
    metadata *about* the source scene, not a copy of the product itself:
    `download_path` points at whatever was actually retrieved (a quicklook
    or a capped-size product), which may be None if download was skipped or
    failed while the scene was still real and identified.
    """

    __tablename__ = "satellite_scenes"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)

    processing_job_id: Mapped[uuid.UUID] = mapped_column(
        GUID(),
        ForeignKey("processing_jobs.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )

    # 'copernicus' today; kept as a plain string (not an enum) so a second
    # provider can be added later without a migration — same reasoning as
    # ProcessingJob.status.
    provider: Mapped[str] = mapped_column(String(32), nullable=False, default="copernicus")

    product_id: Mapped[str] = mapped_column(String(255), nullable=False)
    product_name: Mapped[str] = mapped_column(String(512), nullable=False)
    collection: Mapped[str] = mapped_column(String(64), nullable=False, default="SENTINEL-2")
    platform: Mapped[str | None] = mapped_column(String(64), nullable=True)
    instrument: Mapped[str | None] = mapped_column(String(64), nullable=True)

    acquisition_datetime: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    cloud_cover: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Real GeoJSON geometry (Polygon) as returned by Copernicus' GeoFootprint
    # field — kept as JSON rather than a PostGIS geometry column; no spatial
    # queries are run against it in this phase (see docs/ARCHITECTURE.md §5).
    footprint: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    size_bytes: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    source_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)

    download_status: Mapped[str] = mapped_column(
        String(32), nullable=False, default=DownloadStatus.PENDING
    )
    download_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    download_error: Mapped[str | None] = mapped_column(String(1024), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    processing_job: Mapped["ProcessingJob"] = relationship(  # noqa: F821
        back_populates="satellite_scene"
    )
