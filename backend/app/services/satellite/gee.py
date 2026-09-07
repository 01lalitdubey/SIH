"""Google Earth Engine (GEE) satellite provider — Sentinel-2 imagery
accessed through Earth Engine's compute platform rather than the Copernicus
Data Space OData API directly (see copernicus.py for that provider). Same
BaseSatelliteProvider interface, selected via SATELLITE_PROVIDER=gee
(app/core/config.py, app/services/satellite/service.py).

Import of the `ee` package (earthengine-api) is deliberately lazy — done
only inside `_ee()`, never at module import time — so that
SATELLITE_PROVIDER=copernicus (or =fake) never requires the package
installed, the same lazy-import discipline PROCESSOR_MODE uses for torch
(see app/services/processing_service.py._build_processor).

RGB-only, on purpose (see `BANDS` below): the trained Phase 6 EDSRLite
checkpoint has 3 input channels. Using B4/B3/B2 (Red/Green/Blue) keeps this
provider's output shape-compatible with that already-trained model without
retraining it — adding a 4th band (e.g. B8/NIR) would break that
compatibility outright, not just look different.

Reflectance normalization (verified this session, not assumed): Sentinel-2
SR Harmonized bands are uint16 surface reflectance scaled by 10000 (the same
convention already used for training data in ai/datasets/sen2venus.py's
REFLECTANCE_SCALE). SuperResolutionProcessor._load_and_normalize only
distinguishes uint16 vs. 8-bit input via `array.dtype` *after* calling
PIL's `img.convert("RGB")` on whatever file this provider hands it — and a
direct, real test in this session showed that call silently collapses a
16-bit multi-band TIFF to 8-bit using PIL's own arbitrary rescaling, not a
reflectance-aware one (a synthetic 16-bit array with real values up to
~5000 came back post-`.convert("RGB")` as uint8 with a max of 19). Passing
this provider's real (uint16) reflectance straight through as a raw GeoTIFF
would therefore be silently mis-normalized by existing, unmodified
preprocessing — exactly what this phase must not do. So the correct
reflectance/10000 normalization happens once, here, at acquisition time,
producing an already-correct 8-bit RGB TIFF that a second, separate test
this session confirmed round-trips through PIL byte-for-byte with no
further transformation. `_load_and_normalize` is left completely
unmodified; this provider simply hands it a file in the one format that
code path already handles correctly.
"""

import io
import math
from pathlib import Path

import httpx
import numpy as np
import tifffile

from app.core.config import BACKEND_ROOT, get_settings
from app.services.satellite.base import (
    AOIPolygon,
    BaseSatelliteProvider,
    DownloadResult,
    SceneCandidate,
    SearchParams,
)
from app.services.satellite.exceptions import (
    AuthenticationError,
    MissingCredentialsError,
    NoScenesFoundError,
    ProviderUnavailableError,
    SceneDownloadError,
)
from app.services.satellite.storage import BaseSatelliteStorage

COLLECTION = "COPERNICUS/S2_SR_HARMONIZED"  # Sentinel-2 Level-2A surface reflectance
# RGB-only — see module docstring. Do NOT add B8/NIR here without also
# retraining/replacing the checkpoint; this is a hard input-shape contract,
# not a style choice.
BANDS = ["B4", "B3", "B2"]  # Red, Green, Blue, in that exact order
NATIVE_SCALE_METERS = 10  # true native resolution of B2/B3/B4
REFLECTANCE_SCALE = 10000.0  # Sentinel-2 L2A convention — see module docstring

# ee.Image.getDownloadURL's own documented limits (verified from the
# installed earthengine-api source, ee/image.py: "Maximum request size is
# 32 MB, maximum grid dimension is 10000") — this is GEE's real ceiling for
# the synchronous download path this phase uses, not an arbitrary guess.
# Export.image.toDrive/toCloudStorage (for larger AOIs) needs asynchronous
# task tracking/polling and is explicitly out of scope for this phase.
MAX_SYNC_DOWNLOAD_BYTES = 32 * 1024 * 1024
BYTES_PER_PIXEL_PER_BAND = 2  # uint16 SR reflectance
# Conservative flat-Earth approximation for this pre-flight size estimate
# only (not a geospatial computation — see docs/ARCHITECTURE.md for why
# CRS-aware distance is explicitly Phase 7 territory).
METERS_PER_DEGREE = 111_320


class GEESatelliteProvider(BaseSatelliteProvider):
    name = "gee"

    def __init__(self) -> None:
        self._initialized = False

    @property
    def _settings(self):
        return get_settings()

    def _ee(self):
        try:
            import ee
        except ImportError as exc:
            raise ProviderUnavailableError(
                "The 'earthengine-api' package is not installed. Install it "
                "with 'pip install earthengine-api' to use SATELLITE_PROVIDER=gee."
            ) from exc
        return ee

    def authenticate(self) -> None:
        if self._initialized:
            return

        settings = self._settings
        if not (
            settings.gee_project_id
            and settings.gee_service_account_email
            and settings.gee_service_account_key_path
        ):
            raise MissingCredentialsError(
                "Google Earth Engine credentials are not configured "
                "(GEE_PROJECT_ID / GEE_SERVICE_ACCOUNT_EMAIL / "
                "GEE_SERVICE_ACCOUNT_KEY_PATH)."
            )

        key_path = Path(settings.gee_service_account_key_path)
        if not key_path.is_absolute():
            key_path = BACKEND_ROOT / key_path
        if not key_path.is_file():
            raise MissingCredentialsError(
                f"GEE service account key file not found at '{key_path}'."
            )

        ee = self._ee()
        try:
            credentials = ee.ServiceAccountCredentials(
                email=settings.gee_service_account_email, key_file=str(key_path)
            )
            ee.Initialize(credentials, project=settings.gee_project_id)
        except Exception as exc:  # noqa: BLE001 - any auth/init failure is a real, reportable auth error
            raise AuthenticationError(
                f"Google Earth Engine rejected the configured service account: {exc}"
            ) from exc
        self._initialized = True

    def search_scenes(self, params: SearchParams) -> list[SceneCandidate]:
        self.authenticate()
        ee = self._ee()
        aoi = params.aoi

        geometry = ee.Geometry.Rectangle([aoi.west, aoi.south, aoi.east, aoi.north])
        try:
            collection = (
                ee.ImageCollection(COLLECTION)
                .filterBounds(geometry)
                .filterDate(params.start_date.isoformat(), params.end_date.isoformat())
                .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", params.max_cloud_cover))
                .limit(self._settings.satellite_max_scenes_considered)
            )
            info = collection.getInfo()
        except ee.EEException as exc:
            raise ProviderUnavailableError(f"Google Earth Engine search failed: {exc}") from exc
        except httpx.HTTPError as exc:  # google-api-core wraps some transport errors similarly
            raise ProviderUnavailableError(
                "Could not reach Google Earth Engine to search the catalog."
            ) from exc

        features = (info or {}).get("features", [])
        if not features:
            raise NoScenesFoundError(
                "No Sentinel-2 scenes matched this AOI, date range, and "
                "cloud-cover limit (Google Earth Engine)."
            )
        return [_to_candidate(feature, aoi) for feature in features]

    def download_scene(self, scene: SceneCandidate, storage: BaseSatelliteStorage) -> DownloadResult:
        self.authenticate()
        ee = self._ee()

        west, south, east, north = _bbox_from_footprint(scene.footprint)
        aoi = AOIPolygon(north=north, south=south, east=east, west=west)

        if _estimate_request_bytes(aoi) > MAX_SYNC_DOWNLOAD_BYTES:
            raise SceneDownloadError(
                "Selected AOI is too large for synchronous Google Earth Engine "
                "processing. Please select a smaller AOI."
            )

        geometry = ee.Geometry.Rectangle([west, south, east, north])
        try:
            image = ee.Image(scene.product_id).select(BANDS).clip(geometry)
            url = image.getDownloadURL(
                {
                    "region": geometry,
                    "scale": NATIVE_SCALE_METERS,
                    "format": "GEO_TIFF",
                    "crs": "EPSG:4326",
                }
            )
        except ee.EEException as exc:
            raise ProviderUnavailableError(
                f"Could not build a Google Earth Engine download URL: {exc}"
            ) from exc

        settings = self._settings
        try:
            response = httpx.get(
                url,
                timeout=settings.satellite_http_timeout_seconds * 4,
                follow_redirects=True,
            )
        except httpx.TimeoutException as exc:
            raise ProviderUnavailableError(
                "Timed out downloading imagery from Google Earth Engine."
            ) from exc
        except httpx.HTTPError as exc:
            raise ProviderUnavailableError(
                "Could not reach Google Earth Engine to download imagery."
            ) from exc

        if response.status_code == 400 and "too many pixels" in response.text.lower():
            raise SceneDownloadError(
                "Selected AOI is too large for synchronous Google Earth Engine "
                "processing. Please select a smaller AOI."
            )
        if response.status_code >= 500:
            raise ProviderUnavailableError(
                f"Google Earth Engine download service returned HTTP {response.status_code}."
            )
        if response.status_code != 200:
            raise SceneDownloadError(
                f"Google Earth Engine imagery download failed (HTTP {response.status_code})."
            )
        if not response.content:
            raise SceneDownloadError("Downloaded Google Earth Engine imagery was empty.")

        max_bytes = settings.satellite_max_download_mb * 1024 * 1024
        if len(response.content) > max_bytes:
            raise SceneDownloadError(
                f"Downloaded Google Earth Engine imagery is over the "
                f"{settings.satellite_max_download_mb}MB retrieval cap."
            )

        try:
            raw_array = tifffile.imread(io.BytesIO(response.content))
        except Exception as exc:  # noqa: BLE001 - any decode failure is a real, reportable download error
            raise SceneDownloadError(
                f"Downloaded Google Earth Engine imagery could not be decoded: {exc}"
            ) from exc

        try:
            rgb_uint8 = _reflectance_to_uint8_rgb(raw_array)
        except ValueError as exc:
            raise SceneDownloadError(
                f"Downloaded Google Earth Engine imagery had an unexpected shape: {exc}"
            ) from exc

        buffer = io.BytesIO()
        tifffile.imwrite(buffer, rgb_uint8, photometric="rgb")
        content = buffer.getvalue()

        # GEE asset ids contain '/' (e.g. "COPERNICUS/S2_SR_HARMONIZED/2023...")
        # — LocalSatelliteStorage.save() only mkdir's the scene-id directory
        # itself, not any further nesting a '/' in `filename` would imply, so
        # passing the raw asset id through unsanitized would raise
        # FileNotFoundError on write. Copernicus's product_id (a plain UUID)
        # never hit this; verified by reading storage.py, not assumed.
        safe_id = scene.product_id.replace("/", "_")
        path = storage.save(safe_id, f"{safe_id}.tif", content)
        return DownloadResult(file_path=path, size_bytes=len(content), content_type="image/tiff")


def _to_candidate(feature: dict, aoi: AOIPolygon) -> SceneCandidate:
    """Converts one Earth Engine ImageCollection.getInfo() feature into the
    provider-agnostic SceneCandidate shape. `footprint` deliberately stores
    the *requested AOI* rectangle, not a per-image geometry fetched from
    Earth Engine — this provider doesn't make a second per-candidate call to
    fetch each image's real footprint (untested/unverified without live
    credentials, and not needed for ranking within this phase — see
    BaseSatelliteProvider.select_best_scene, which only needs bounding-box
    overlap). This is the documented fallback the Phase 6.3 brief allows:
    an honest AOI representation, not a claim of a verified scene footprint.
    """
    props = feature.get("properties", {}) or {}
    asset_id = feature.get("id") or props.get("system:index")

    acquisition_dt = None
    time_start_ms = props.get("system:time_start")
    if time_start_ms is not None:
        from datetime import datetime, timezone

        acquisition_dt = datetime.fromtimestamp(time_start_ms / 1000, tz=timezone.utc)

    platform_id = props.get("SPACECRAFT_NAME")  # e.g. "Sentinel-2A"

    return SceneCandidate(
        product_id=asset_id,
        name=props.get("PRODUCT_ID", asset_id),
        collection="SENTINEL-2",
        platform=platform_id,
        instrument="MSI",
        acquisition_datetime=acquisition_dt,
        cloud_cover=props.get("CLOUDY_PIXEL_PERCENTAGE"),
        footprint=aoi.to_geojson(),
        size_bytes=None,  # not known ahead of getDownloadURL; GEE search metadata doesn't include it
        source_url=f"https://code.earthengine.google.com/?asset={asset_id}" if asset_id else None,
    )


def _bbox_from_footprint(footprint: dict | None) -> tuple[float, float, float, float]:
    if not footprint or footprint.get("type") != "Polygon":
        raise SceneDownloadError("Selected scene has no usable AOI geometry to re-request.")
    coords = footprint.get("coordinates")
    if not coords or not coords[0]:
        raise SceneDownloadError("Selected scene has no usable AOI geometry to re-request.")
    lons = [pt[0] for pt in coords[0]]
    lats = [pt[1] for pt in coords[0]]
    return min(lons), min(lats), max(lons), max(lats)  # west, south, east, north


def _estimate_request_bytes(aoi: AOIPolygon) -> int:
    width_m = (aoi.east - aoi.west) * METERS_PER_DEGREE
    height_m = (aoi.north - aoi.south) * METERS_PER_DEGREE
    width_px = max(1, math.ceil(width_m / NATIVE_SCALE_METERS))
    height_px = max(1, math.ceil(height_m / NATIVE_SCALE_METERS))
    return width_px * height_px * len(BANDS) * BYTES_PER_PIXEL_PER_BAND


def _to_band_first(array: np.ndarray) -> np.ndarray:
    """Handles either (bands, H, W) or (H, W, bands) — see module docstring;
    GeoTIFF band ordering from different encoders isn't assumed."""
    if array.ndim != 3:
        raise ValueError(f"expected a 3-band raster, got array with shape {array.shape}")
    if array.shape[0] == len(BANDS):
        return array
    if array.shape[-1] == len(BANDS):
        return array.transpose(2, 0, 1)
    raise ValueError(f"expected a {len(BANDS)}-band raster, got array with shape {array.shape}")


def _reflectance_to_uint8_rgb(raw_array: np.ndarray) -> np.ndarray:
    """Real Sentinel-2 SR reflectance (uint16, scaled by REFLECTANCE_SCALE)
    -> normalized, clipped, 8-bit RGB — see module docstring for exactly why
    this happens here rather than being left to SuperResolutionProcessor's
    existing (unmodified) preprocessing."""
    band_first = _to_band_first(raw_array).astype(np.float32)
    normalized = np.clip(band_first / REFLECTANCE_SCALE, 0.0, 1.0)
    uint8 = (normalized * 255.0).round().astype(np.uint8)
    return uint8.transpose(1, 2, 0)  # (C, H, W) -> (H, W, C) for tifffile's photometric='rgb'
