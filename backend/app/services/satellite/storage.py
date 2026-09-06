"""Where downloaded satellite bytes end up on disk.

Kept separate from BaseSatelliteProvider so a provider's HTTP/auth logic
never touches a filesystem path directly — the same reasoning as
docs/ARCHITECTURE.md §9 (storage-adapter interface for uploads/results).
Local disk is acceptable for Phase 5; S3/MinIO would be a second
implementation of this same interface, not a rewrite of the providers.
"""

from abc import ABC, abstractmethod
from pathlib import Path

from app.core.config import get_settings


class BaseSatelliteStorage(ABC):
    @abstractmethod
    def save(self, scene_id: str, filename: str, content: bytes) -> str:
        """Persists `content` and returns the path it was stored at."""
        raise NotImplementedError


class LocalSatelliteStorage(BaseSatelliteStorage):
    def save(self, scene_id: str, filename: str, content: bytes) -> str:
        settings = get_settings()
        scene_dir = settings.satellite_path / scene_id
        scene_dir.mkdir(parents=True, exist_ok=True)
        destination = scene_dir / filename
        destination.write_bytes(content)
        return str(destination)
