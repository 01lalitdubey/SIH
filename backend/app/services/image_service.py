import uuid

from fastapi import UploadFile
from PIL import Image as PILImage
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.image import Image
from app.utils.file_utils import (
    generate_stored_filename,
    is_allowed_upload,
    sanitize_filename,
)

settings = get_settings()


class UnsupportedFileType(ValueError):
    pass


class FileTooLarge(ValueError):
    pass


class InvalidImage(ValueError):
    pass


async def save_upload(db: Session, file: UploadFile) -> Image:
    original_name = sanitize_filename(file.filename or "upload")

    if not is_allowed_upload(original_name, file.content_type):
        raise UnsupportedFileType(
            f"Unsupported file type for '{original_name}'. "
            "Allowed: jpg, jpeg, png, tif, tiff, webp."
        )

    max_bytes = settings.max_upload_size_mb * 1024 * 1024
    content = await file.read()
    if len(content) > max_bytes:
        raise FileTooLarge(f"File exceeds the {settings.max_upload_size_mb}MB upload limit.")
    if len(content) == 0:
        raise InvalidImage("Uploaded file is empty.")

    stored_filename = generate_stored_filename(original_name)
    destination = settings.upload_path / stored_filename
    destination.write_bytes(content)

    width: int | None = None
    height: int | None = None
    try:
        with PILImage.open(destination) as img:
            width, height = img.size
    except Exception:
        # Not every accepted format (e.g. some GeoTIFFs) is guaranteed to be
        # readable by Pillow; dimensions stay null rather than failing the
        # whole upload. Satellite-specific validation lands in Phase 5.
        width, height = None, None

    image = Image(
        filename=original_name,
        stored_filename=stored_filename,
        file_path=str(destination),
        file_type=file.content_type or "application/octet-stream",
        file_size=len(content),
        width=width,
        height=height,
    )
    db.add(image)
    db.commit()
    db.refresh(image)
    return image


def list_images(db: Session, limit: int = 50, offset: int = 0) -> list[Image]:
    stmt = select(Image).order_by(Image.created_at.desc()).limit(limit).offset(offset)
    return list(db.scalars(stmt).all())


def get_image(db: Session, image_id: uuid.UUID) -> Image | None:
    return db.get(Image, image_id)
