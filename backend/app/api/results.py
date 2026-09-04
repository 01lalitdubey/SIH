import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.processing_job import JobStatus
from app.schemas.result import ResultOut
from app.services import processing_service, result_service

router = APIRouter(prefix="/results", tags=["results"])


@router.get("/{job_id}", response_model=ResultOut)
def get_result(job_id: uuid.UUID, db: Session = Depends(get_db)) -> ResultOut:
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
