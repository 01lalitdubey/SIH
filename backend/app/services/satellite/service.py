"""SatelliteService — the one thing the rest of the backend talks to.

    ProcessingService
          |
          v
    SatelliteService (this module)
          |
          v
    BaseSatelliteProvider  ->  CopernicusSatelliteProvider (real)
          |
          v
    BaseSatelliteStorage   ->  LocalSatelliteStorage (real)

Owns AOI/date/cloud-cover validation, calls the provider through the
authenticate -> search -> select -> download sequence, and persists exactly
one SatelliteScene row per job — on a download failure that row still gets
written (with download_status='failed') so a real, identified scene isn't
silently lost even when its data couldn't be retrieved.

`_provider` is a module-level singleton, same pattern as
processing_service._processor — tests replace it with FakeSatelliteProvider
via monkeypatch (see tests/conftest.py) so the suite never touches the
network.
"""

from datetime import date, datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.models.processing_job import ProcessingJob
from app.models.satellite_scene import DownloadStatus, SatelliteScene
from app.services.satellite.base import AOIPolygon, BaseSatelliteProvider, SearchParams
from app.services.satellite.copernicus import CopernicusSatelliteProvider
from app.services.satellite.exceptions import (
    InvalidAOIError,
    InvalidCloudCoverError,
    InvalidDateRangeError,
    SatelliteError,
    SceneDownloadError,
)
from app.services.satellite.storage import BaseSatelliteStorage, LocalSatelliteStorage

DEFAULT_SEARCH_WINDOW_DAYS = 30
DEFAULT_MAX_CLOUD_COVER = 20.0
MAX_SEARCH_WINDOW_DAYS = 366

_provider: BaseSatelliteProvider = CopernicusSatelliteProvider()
_storage: BaseSatelliteStorage = LocalSatelliteStorage()


def build_search_params(aoi_geometry: dict) -> SearchParams:
    """Validates and resolves one AOI-driven job's search parameters.

    `aoi_geometry` is exactly what's stored on ProcessingJob.aoi_geometry —
    the frontend's {north, south, east, west}, plus an optional nested
    "search" object ({start_date, end_date, max_cloud_cover}) the frontend
    doesn't send yet (Phase 5 applies sensible defaults instead — see
    docs/ARCHITECTURE.md). Raises Invalid*Error for genuinely malformed
    input; never silently accepts it.
    """
    aoi = _validate_aoi(aoi_geometry)
    search_input = aoi_geometry.get("search") or {}
    start_date, end_date = _resolve_date_range(
        search_input.get("start_date"), search_input.get("end_date")
    )
    max_cloud_cover = _resolve_cloud_cover(search_input.get("max_cloud_cover"))
    return SearchParams(
        aoi=aoi, start_date=start_date, end_date=end_date, max_cloud_cover=max_cloud_cover
    )


def acquire_scene_for_job(db: Session, job: ProcessingJob) -> SatelliteScene:
    """Runs the full AOI -> search -> select -> download sequence for one
    job and persists the outcome. Raises SatelliteError (or a subclass) on
    any failure that should fail the job — the caller (processing_service)
    is responsible for turning that into job.status = 'failed'."""
    if not job.aoi_geometry:
        raise InvalidAOIError("Job has no AOI geometry to search with.")

    params = build_search_params(job.aoi_geometry)

    _provider.authenticate()
    candidates = _provider.search_scenes(params)
    selected = _provider.select_best_scene(candidates, params)

    scene = SatelliteScene(
        processing_job_id=job.id,
        provider=_provider.name,
        product_id=selected.product_id,
        product_name=selected.name,
        collection=selected.collection,
        platform=selected.platform,
        instrument=selected.instrument,
        acquisition_datetime=selected.acquisition_datetime,
        cloud_cover=selected.cloud_cover,
        footprint=selected.footprint,
        size_bytes=selected.size_bytes,
        source_url=selected.source_url,
        download_status=DownloadStatus.DOWNLOADING,
    )
    db.add(scene)
    db.commit()
    db.refresh(scene)

    try:
        result = _provider.download_scene(selected, _storage)
    except SceneDownloadError as exc:
        scene.download_status = DownloadStatus.FAILED
        scene.download_error = str(exc)
        db.commit()
        raise
    except SatelliteError:
        scene.download_status = DownloadStatus.FAILED
        scene.download_error = "Provider became unavailable during download."
        db.commit()
        raise

    scene.download_status = DownloadStatus.COMPLETED
    scene.download_path = result.file_path
    db.commit()
    db.refresh(scene)
    return scene


def _validate_aoi(aoi_geometry: dict) -> AOIPolygon:
    try:
        north = float(aoi_geometry["north"])
        south = float(aoi_geometry["south"])
        east = float(aoi_geometry["east"])
        west = float(aoi_geometry["west"])
    except (KeyError, TypeError, ValueError) as exc:
        raise InvalidAOIError("AOI geometry is missing north/south/east/west bounds.") from exc

    if not (-90 <= south <= 90 and -90 <= north <= 90):
        raise InvalidAOIError("AOI latitude must be between -90 and 90 degrees.")
    if not (-180 <= west <= 180 and -180 <= east <= 180):
        raise InvalidAOIError("AOI longitude must be between -180 and 180 degrees.")
    if north <= south:
        raise InvalidAOIError("AOI 'north' bound must be greater than 'south'.")
    if east <= west:
        raise InvalidAOIError("AOI 'east' bound must be greater than 'west'.")

    return AOIPolygon(north=north, south=south, east=east, west=west)


def _resolve_date_range(start_raw: str | None, end_raw: str | None) -> tuple[date, date]:
    today = datetime.now(timezone.utc).date()

    if start_raw is None and end_raw is None:
        return today - timedelta(days=DEFAULT_SEARCH_WINDOW_DAYS), today

    try:
        start_date = date.fromisoformat(start_raw) if start_raw else today - timedelta(
            days=DEFAULT_SEARCH_WINDOW_DAYS
        )
        end_date = date.fromisoformat(end_raw) if end_raw else today
    except ValueError as exc:
        raise InvalidDateRangeError("start_date/end_date must be ISO 8601 dates (YYYY-MM-DD).") from exc

    if start_date >= end_date:
        raise InvalidDateRangeError("start_date must be earlier than end_date.")
    if (end_date - start_date).days > MAX_SEARCH_WINDOW_DAYS:
        raise InvalidDateRangeError(
            f"Search window cannot exceed {MAX_SEARCH_WINDOW_DAYS} days."
        )
    return start_date, end_date


def _resolve_cloud_cover(raw: float | None) -> float:
    if raw is None:
        return DEFAULT_MAX_CLOUD_COVER
    try:
        value = float(raw)
    except (TypeError, ValueError) as exc:
        raise InvalidCloudCoverError("max_cloud_cover must be a number between 0 and 100.") from exc
    if not (0 <= value <= 100):
        raise InvalidCloudCoverError("max_cloud_cover must be between 0 and 100.")
    return value
