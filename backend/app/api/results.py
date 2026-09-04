import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.processing_job import JobStatus
from app.schemas.result import ResultOut
from app.services import processing_service, result_service

router = APIRouter(prefix="/results", tags=["results"])


def _get_completed_result(db: Session, job_id: uuid.UUID):
    job = processing_service.get_job(db, job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")

    if job.status != JobStatus.COMPLETED:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Result not available yet — job status is '{job.status}'",
        )

    result = result_service.get_result_by_job(db, job_id)
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Result not found")

    return job, result


@router.get("/{job_id}", response_model=ResultOut)
def get_result(job_id: uuid.UUID, db: Session = Depends(get_db)) -> ResultOut:
    job, result = _get_completed_result(db, job_id)

    return ResultOut(
        job_id=job.id,
        status=job.status,
        output_path=result.output_path,
        psnr=result.psnr,
        ssim=result.ssim,
        lpips=result.lpips,
        processing_time=result.processing_time,
        output_width=result.output_width,
        output_height=result.output_height,
        created_at=result.created_at,
    )


@router.get("/{job_id}/file")
def get_result_file(job_id: uuid.UUID, db: Session = Depends(get_db)) -> FileResponse:
    """Serves the mock processing output by DB-verified job id. AOI-only
    jobs (no uploaded image) have no output file — see MockProcessor — so
    this 404s for those even though the job itself completed."""
    _job, result = _get_completed_result(db, job_id)

    if not result.output_path:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="This job has no output file (AOI-only jobs don't generate one yet)",
        )

    path = Path(result.output_path)
    if not path.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Output file missing")

    return FileResponse(path, media_type="image/png", filename=path.name)
