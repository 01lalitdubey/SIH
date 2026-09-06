import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class SatelliteSceneOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    provider: str
    product_id: str
    product_name: str
    collection: str
    platform: str | None
    instrument: str | None
    acquisition_datetime: datetime | None
    cloud_cover: float | None
    footprint: dict | None
    size_bytes: int | None
    download_status: str
    download_error: str | None
    created_at: datetime
