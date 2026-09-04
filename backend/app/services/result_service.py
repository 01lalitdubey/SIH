import uuid

from sqlalchemy.orm import Session

from app.models.result import Result


def get_result_by_job(db: Session, job_id: uuid.UUID) -> Result | None:
    return db.query(Result).filter(Result.job_id == job_id).first()
