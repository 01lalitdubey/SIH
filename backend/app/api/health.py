from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import get_db
from app.services import processing_service

router = APIRouter(tags=["health"])


@router.get("/health")
def health_check(db: Session = Depends(get_db)) -> dict:
    try:
        db.execute(text("SELECT 1"))
        db_status = "connected"
    except Exception as exc:  # pragma: no cover - only hit if DB is down
        db_status = f"unavailable: {exc}"

    # Phase 6.1: the frontend reads this instead of hardcoding whether real
    # AI inference is active — see processing_service.get_processor_status.
    processor_status = processing_service.get_processor_status()

    return {
        "status": "ok",
        "service": "srm-backend",
        "database": db_status,
        # Phase 6.3: which satellite provider AOI jobs will use — just the
        # configured name, not live readiness (unlike processor_status
        # above, checking that would mean a real network call to Copernicus
        # or GEE on every health check, which this endpoint doesn't do).
        "satellite_provider": get_settings().satellite_provider,
        **processor_status,
    }
