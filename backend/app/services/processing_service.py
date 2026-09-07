import uuid
from datetime import datetime, timezone

from fastapi import BackgroundTasks
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core import database as db_module
from app.core.config import get_settings
from app.models.processing_job import JobStatus, ProcessingJob
from app.schemas.processing import ProcessingCreateRequest
from app.services.processors.mock_processor import MockProcessor
from app.services.satellite import service as satellite_service
from app.services.satellite.exceptions import SatelliteError


def _build_processor():
    """PROCESSOR_MODE selects the real implementation behind BaseProcessor.
    'super_resolution' is never silently downgraded to 'mock' — an unknown
    mode is a startup-time config error, not a quiet fallback. The heavy
    ai.* / torch import only happens when super_resolution mode is actually
    requested, so a 'mock'-mode deployment never needs PyTorch installed."""
    mode = get_settings().processor_mode
    if mode == "mock":
        return MockProcessor()
    if mode == "super_resolution":
        from app.services.processors.super_resolution_processor import SuperResolutionProcessor

        return SuperResolutionProcessor()
    raise ValueError(f"Unknown PROCESSOR_MODE '{mode}'. Expected 'mock' or 'super_resolution'.")


# Single shared instance — swapping processors is this one call, not a
# rewrite of ProcessingService. PROCESSOR_MODE is read once at process
# startup; changing it requires restarting the backend, same as any other
# env-driven setting in this app.
_processor = _build_processor()


def get_processor_status(processor=None) -> dict:
    """Real, introspected state of the active processor — used by the
    /health endpoint (and the frontend, via it) so the UI never has to
    guess or hardcode whether real AI inference is active. Duck-types on
    `_engine` instead of `isinstance(processor, SuperResolutionProcessor)`
    so this never imports that module (and therefore never imports torch)
    when running in mock mode — see _build_processor's docstring."""
    processor = _processor if processor is None else processor
    mode = get_settings().processor_mode

    if not hasattr(processor, "_engine"):
        return {
            "processor_mode": mode,
            "is_mock": True,
            "processor_ready": True,
            "model_name": None,
            "model_version": None,
            "device": None,
            "scale_factor": None,
            "processor_error": None,
        }

    engine = processor._engine
    if engine is None:
        return {
            "processor_mode": mode,
            "is_mock": False,
            "processor_ready": False,
            "model_name": None,
            "model_version": None,
            "device": None,
            "scale_factor": None,
            "processor_error": processor._init_error,
        }

    return {
        "processor_mode": mode,
        "is_mock": False,
        "processor_ready": True,
        "model_name": engine.checkpoint_metadata.get("model_name", "edsr_satellite"),
        "model_version": f"scale{engine.scale_factor}x",
        "device": str(engine.device),
        "scale_factor": engine.scale_factor,
        "processor_error": None,
    }

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
