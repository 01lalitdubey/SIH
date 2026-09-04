import uuid

from fastapi import BackgroundTasks
from sqlalchemy.orm import Session

from app.models.processing_job import JobStatus, ProcessingJob
from app.schemas.processing import ProcessingCreateRequest
from app.services.processors.mock_processor import MockProcessor

# Single shared instance — MockProcessor holds no per-request state, it just
# implements BaseProcessor.run(job_id). Swapping in a real processor later
# means changing this one line.
_processor = MockProcessor()


def create_job(
    db: Session, payload: ProcessingCreateRequest, background_tasks: BackgroundTasks
) -> ProcessingJob:
    job = ProcessingJob(
        image_id=payload.image_id,
        analysis_name=payload.analysis_name,
        scale_factor=payload.scale_factor,
        aoi_geometry=payload.aoi.model_dump() if payload.aoi else None,
        simulate_failure=payload.simulate_failure,
        status=JobStatus.QUEUED,
        progress=0,
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    background_tasks.add_task(_processor.run, job.id)
    return job


def get_job(db: Session, job_id: uuid.UUID) -> ProcessingJob | None:
    return db.get(ProcessingJob, job_id)
