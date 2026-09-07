from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_ROOT = Path(__file__).resolve().parent.parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    database_url: str = "postgresql+psycopg2://srm:srm_dev_password@localhost:5433/srm_db"
    upload_dir: str = "uploads"
    output_dir: str = "outputs"
    cors_origins: str = "http://localhost:5173"
    env: str = "development"

    max_upload_size_mb: int = 25

    # --- Phase 5: Copernicus Data Space Ecosystem (Sentinel-2) -------------
    # Left blank by default. When unset, satellite search endpoints return a
    # clear 503 (MissingCredentialsError) instead of silently mocking data.
    copernicus_client_id: str | None = None
    copernicus_client_secret: str | None = None
    copernicus_token_url: str = (
        "https://identity.dataspace.copernicus.eu/auth/realms/CDSE/protocol/openid-connect/token"
    )
    copernicus_catalog_url: str = "https://catalogue.dataspace.copernicus.eu/odata/v1"
    copernicus_download_url: str = "https://zipper.dataspace.copernicus.eu/odata/v1"

    satellite_dir: str = "satellite"
    # Full Sentinel-2 SAFE products are commonly 700MB-1GB (confirmed against
    # the live catalog during Phase 5 development). This is a deliberate
    # safety cap, not a bug — see docs/ARCHITECTURE.md Phase 5 section.
    satellite_max_download_mb: int = 200
    satellite_http_timeout_seconds: float = 30.0
    satellite_max_scenes_considered: int = 20

    # --- Phase 6: AI super-resolution ---------------------------------------
    # 'mock' (default, safe) or 'super_resolution' (real PyTorch inference).
    # Never silently falls back from super_resolution to mock — see
    # app/services/processors/super_resolution_processor.py.
    processor_mode: str = "mock"
    sr_checkpoint_path: str = "ai/checkpoints/edsr_satellite.pt"
    # None = auto-detect (CUDA if available, else CPU) — see ai/inference/infer.py.
    sr_device: str | None = None

    @property
    def sr_checkpoint_full_path(self) -> Path:
        return BACKEND_ROOT / self.sr_checkpoint_path

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def upload_path(self) -> Path:
        path = BACKEND_ROOT / self.upload_dir
        path.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def output_path(self) -> Path:
        path = BACKEND_ROOT / self.output_dir
        path.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def satellite_path(self) -> Path:
        path = BACKEND_ROOT / self.satellite_dir
        path.mkdir(parents=True, exist_ok=True)
        return path


@lru_cache
def get_settings() -> Settings:
    return Settings()
