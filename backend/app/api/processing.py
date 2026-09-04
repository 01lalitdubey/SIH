import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.processing import ProcessingCreateRequest, ProcessingJobOut
from app.services import image_service, processing_service

router = APIRouter(prefix="/process", tags=["processing"])


@router.post("", response_model=ProcessingJobOut, status_code=status.HTTP_201_CREATED)
def create_processing_job(
    payload: ProcessingCreateRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
) -> ProcessingJobOut:
    if payload.image_id is not None:
        image = image_service.get_image(db, payload.image_id)
        if image is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Image {payload.image_id} not found",
            )

    job = processing_service.create_job(db, payload, background_tasks)
    return job


@router.get("", response_model=list[ProcessingJobOut])
def list_processing_jobs(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> list[ProcessingJobOut]:
    return processing_service.list_jobs(db, limit=limit, offset=offset)


@router.get("/{job_id}", response_model=ProcessingJobOut)
def get_processing_job(job_id: uuid.UUID, db: Session = Depends(get_db)) -> ProcessingJobOut:
    job = processing_service.get_job(db, job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    return job
