import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.satellite_scene import DownloadStatus, SatelliteScene
from app.schemas.satellite import SatelliteSceneOut

router = APIRouter(prefix="/satellite", tags=["satellite"])


def _get_scene_or_404(db: Session, scene_id: uuid.UUID) -> SatelliteScene:
    scene = db.get(SatelliteScene, scene_id)
    if scene is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Satellite scene not found")
    return scene


@router.get("/scenes/{scene_id}", response_model=SatelliteSceneOut)
def get_scene(scene_id: uuid.UUID, db: Session = Depends(get_db)) -> SatelliteSceneOut:
    return _get_scene_or_404(db, scene_id)


@router.get("/scenes/{scene_id}/file")
def get_scene_file(scene_id: uuid.UUID, db: Session = Depends(get_db)) -> FileResponse:
    """Serves whatever was actually retrieved for this scene (a quicklook,
    or a capped-size product), by DB-verified id — same pattern as
    /images/{id}/file and /results/{job_id}/file, never a raw client path."""
    scene = _get_scene_or_404(db, scene_id)

    if scene.download_status != DownloadStatus.COMPLETED or not scene.download_path:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No downloaded file for this scene (download_status: {scene.download_status})",
        )

    path = Path(scene.download_path)
    if not path.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Scene file missing on disk")

    return FileResponse(path, filename=path.name)
