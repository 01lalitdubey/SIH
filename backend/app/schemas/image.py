import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ImageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    filename: str
    stored_filename: str
    file_type: str
    file_size: int
    width: int | None = None
    height: int | None = None
    image_metadata: dict | None = None
    created_at: datetime
