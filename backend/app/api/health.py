from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.database import get_db

router = APIRouter(tags=["health"])


@router.get("/health")
def health_check(db: Session = Depends(get_db)) -> dict:
    try:
        db.execute(text("SELECT 1"))
        db_status = "connected"
    except Exception as exc:  # pragma: no cover - only hit if DB is down
        db_status = f"unavailable: {exc}"

    return {
        "status": "ok",
        "service": "srm-backend",
        "database": db_status,
    }
