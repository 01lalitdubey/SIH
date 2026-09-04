import uuid

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.image import ImageOut
from app.services import image_service

router = APIRouter(prefix="/images", tags=["images"])


@router.post("/upload", response_model=ImageOut, status_code=status.HTTP_201_CREATED)
async def upload_image(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
) -> ImageOut:
    try:
        image = await image_service.save_upload(db, file)
    except image_service.UnsupportedFileType as exc:
        raise HTTPException(status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail=str(exc))
    except image_service.FileTooLarge as exc:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail=str(exc)
        )
    except image_service.InvalidImage as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    return image


@router.get("", response_model=list[ImageOut])
def list_images(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> list[ImageOut]:
    return image_service.list_images(db, limit=limit, offset=offset)


@router.get("/{image_id}", response_model=ImageOut)
def get_image(image_id: uuid.UUID, db: Session = Depends(get_db)) -> ImageOut:
    image = image_service.get_image(db, image_id)
    if image is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Image not found")
    return image
