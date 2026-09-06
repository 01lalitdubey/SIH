import uuid
from datetime import datetime, timezone

from fastapi import BackgroundTasks
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core import database as db_module
from app.models.processing_job import JobStatus, ProcessingJob
from app.schemas.processing import ProcessingCreateRequest
from app.services.processors.mock_processor import MockProcessor
from app.services.satellite import service as satellite_service
from app.services.satellite.exceptions import SatelliteError

# Single shared instance — MockProcessor holds no per-request state, it just
# implements BaseProcessor.run(job_id). Swapping in a real processor later
# means changing this one line.
_processor = MockProcessor()

# A stage marker for AOI-driven jobs, distinct from ProcessingStage.ORDERED
# (Phase 3/4's five mock stages). The existing frontend's stageKeyToIndex()
# returns -1 for any stage it doesn't recognize, which renders every stage
# as "pending" — a safe, non-breaking fallback (see jobStatus.js) rather
# than a new dedicated UI, which is out of scope per the frontend-frozen
# constraint for this phase.
SATELLITE_STAGE = "satellite_acquisition"


def create_job(
    db: Session, payload: ProcessingCreateRequest, background_tasks: BackgroundTasks
) -> ProcessingJob:
    aoi_geometry = None
    if payload.aoi:
        aoi_geometry = payload.aoi.model_dump()
        aoi_geometry["search"] = {
            "start_date": payload.start_date.isoformat() if payload.start_date else None,
            "end_date": payload.end_date.isoformat() if payload.end_date else None,
            "max_cloud_cover": payload.max_cloud_cover,
        }

    job = ProcessingJob(
        image_id=payload.image_id,
        analysis_name=payload.analysis_name,
        scale_factor=payload.scale_factor,
        aoi_geometry=aoi_geometry,
        simulate_failure=payload.simulate_failure,
        status=JobStatus.QUEUED,
        progress=0,
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    background_tasks.add_task(_run_job_pipeline, job.id)
    return job


def _run_job_pipeline(job_id: uuid.UUID) -> None:
    """AOI -> SatelliteService -> (real) scene acquisition -> MockProcessor.

    Image-driven jobs are untouched — this only adds a step in front of the
    existing (unmodified) MockProcessor for jobs that came from an AOI. A
    failure here fails the job outright; it never falls through to
    MockProcessor and reports a false "completed" (per Phase 5 requirement:
    a failed satellite download must not look like a successful job).
    """
    session = db_module.SessionLocal()
    try:
        job = session.get(ProcessingJob, job_id)
        if job is None:
            return

        if job.aoi_geometry is not None:
            job.status = JobStatus.PROCESSING
            job.current_stage = SATELLITE_STAGE
            job.started_at = job.started_at or datetime.now(timezone.utc)
            job.progress = 5
            session.commit()

            try:
                satellite_service.acquire_scene_for_job(session, job)
            except SatelliteError as exc:
                job.status = JobStatus.FAILED
                job.error_message = f"Satellite acquisition failed: {exc}"
                job.completed_at = datetime.now(timezone.utc)
                session.commit()
                return

            job.current_stage = None
            session.commit()
    finally:
        session.close()

    _processor.run(job_id)


def get_job(db: Session, job_id: uuid.UUID) -> ProcessingJob | None:
    return db.get(ProcessingJob, job_id)


def list_jobs(db: Session, limit: int = 50, offset: int = 0) -> list[ProcessingJob]:
    stmt = (
        select(ProcessingJob)
        .order_by(ProcessingJob.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return list(db.scalars(stmt).all())
