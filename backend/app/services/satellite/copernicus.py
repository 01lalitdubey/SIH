"""Real Copernicus Data Space Ecosystem (CDSE) integration for Sentinel-2.

Endpoints and query syntax below were verified against the live CDSE API
during Phase 5 development (unauthenticated GETs — the catalog search is
publicly readable; only download requires a bearer token):

  - Catalog search:  GET {catalog_url}/Products?$filter=...&$expand=Attributes
    Confirmed live: AOI polygon intersection via OData.CSC.Intersects,
    ContentDate/Start range filtering, and server-side cloud-cover /
    processing-level filtering via Attributes/OData.CSC.{Double,String}Attribute
    all compose correctly in a single $filter.
  - Token endpoint:  POST {token_url}  (grant_type=client_credentials)
  - Download:        GET {download_url}/Products({id})/$value  (Bearer token)

What is NOT verified live: the authenticated code paths (token exchange,
download), because this development environment has no real
COPERNICUS_CLIENT_ID/SECRET. See backend/README.md "Live Copernicus
verification" for exactly what was and wasn't exercised against the real
API, and why.
"""

import time
from datetime import date, datetime, timezone

import httpx

from app.core.config import get_settings
from app.services.satellite.base import (
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

COLLECTION = "SENTINEL-2"
# Surface-reflectance, atmospherically corrected — the standard analysis-
# ready Sentinel-2 product, preferred over raw L1C top-of-atmosphere data.
PROCESSING_LEVEL = "S2MSI2A"


class CopernicusSatelliteProvider(BaseSatelliteProvider):
    name = "copernicus"

    def __init__(self) -> None:
        self._access_token: str | None = None
        self._token_expires_at: float = 0.0

    @property
    def _settings(self):
        return get_settings()

    def authenticate(self) -> None:
        settings = self._settings
        if not settings.copernicus_client_id or not settings.copernicus_client_secret:
            raise MissingCredentialsError(
                "Copernicus credentials are not configured "
                "(COPERNICUS_CLIENT_ID / COPERNICUS_CLIENT_SECRET)."
            )

        if self._access_token and time.monotonic() < self._token_expires_at:
            return  # cached token still valid

        try:
            response = httpx.post(
                settings.copernicus_token_url,
                data={
                    "grant_type": "client_credentials",
                    "client_id": settings.copernicus_client_id,
                    "client_secret": settings.copernicus_client_secret,
                },
                timeout=settings.satellite_http_timeout_seconds,
            )
        except httpx.TimeoutException as exc:
            raise ProviderUnavailableError(
                "Timed out contacting the Copernicus identity service."
            ) from exc
        except httpx.HTTPError as exc:
            raise ProviderUnavailableError(
                "Could not reach the Copernicus identity service."
            ) from exc

        if response.status_code in (400, 401, 403):
            raise AuthenticationError(
                "Copernicus rejected the configured client credentials."
            )
        if response.status_code >= 500:
            raise ProviderUnavailableError(
                f"Copernicus identity service returned HTTP {response.status_code}."
            )
        if response.status_code != 200:
            raise ProviderUnavailableError(
                f"Unexpected response from Copernicus identity service "
                f"(HTTP {response.status_code})."
            )

        payload = response.json()
        token = payload.get("access_token")
        if not token:
            raise AuthenticationError("Copernicus token response did not include an access token.")

        self._access_token = token
        # Refresh 30s early to avoid a token expiring mid-request.
        self._token_expires_at = time.monotonic() + max(payload.get("expires_in", 600) - 30, 30)

    def search_scenes(self, params: SearchParams) -> list[SceneCandidate]:
        settings = self._settings
        odata_filter = _build_filter(params)

        try:
            response = httpx.get(
                f"{settings.copernicus_catalog_url}/Products",
                params={
                    "$filter": odata_filter,
                    "$top": settings.satellite_max_scenes_considered,
                    "$orderby": "ContentDate/Start desc",
                    "$expand": "Attributes",
                },
                timeout=settings.satellite_http_timeout_seconds,
            )
        except httpx.TimeoutException as exc:
            raise ProviderUnavailableError("Timed out searching the Copernicus catalog.") from exc
        except httpx.HTTPError as exc:
            raise ProviderUnavailableError("Could not reach the Copernicus catalog.") from exc

        if response.status_code >= 500:
            raise ProviderUnavailableError(
                f"Copernicus catalog returned HTTP {response.status_code}."
            )
        if response.status_code != 200:
            raise ProviderUnavailableError(
                f"Copernicus catalog search failed (HTTP {response.status_code})."
            )

        products = response.json().get("value", [])
        candidates = [_to_candidate(p) for p in products]
        if not candidates:
            raise NoScenesFoundError(
                "No Sentinel-2 scenes matched this AOI, date range, and cloud-cover limit."
            )
        return candidates

    def download_scene(self, scene: SceneCandidate, storage: BaseSatelliteStorage) -> DownloadResult:
        settings = self._settings
        self.authenticate()

        if scene.size_bytes:
            size_mb = scene.size_bytes / (1024 * 1024)
            if size_mb > settings.satellite_max_download_mb:
                raise SceneDownloadError(
                    f"Selected scene '{scene.name}' is {size_mb:.0f}MB, over the "
                    f"{settings.satellite_max_download_mb}MB Phase 5 retrieval cap. "
                    "Full-scene raster download is deferred until band/subset "
                    "selection is added — only scene metadata was stored for this job."
                )

        url = f"{settings.copernicus_download_url}/Products({scene.product_id})/$value"
        headers = {"Authorization": f"Bearer {self._access_token}"}
        max_bytes = settings.satellite_max_download_mb * 1024 * 1024

        try:
            with httpx.stream(
                "GET",
                url,
                headers=headers,
                timeout=settings.satellite_http_timeout_seconds,
                follow_redirects=True,
            ) as response:
                if response.status_code in (401, 403):
                    raise AuthenticationError(
                        "Copernicus rejected the access token while downloading the scene."
                    )
                if response.status_code >= 500:
                    raise ProviderUnavailableError(
                        f"Copernicus download service returned HTTP {response.status_code}."
                    )
                if response.status_code != 200:
                    raise SceneDownloadError(
                        f"Copernicus download failed (HTTP {response.status_code})."
                    )

                chunks = bytearray()
                for chunk in response.iter_bytes():
                    chunks.extend(chunk)
                    if len(chunks) > max_bytes:
                        raise SceneDownloadError(
                            "Download exceeded the configured size cap mid-stream; aborted."
                        )
                content = bytes(chunks)
        except httpx.TimeoutException as exc:
            raise ProviderUnavailableError("Timed out downloading the scene from Copernicus.") from exc
        except httpx.HTTPError as exc:
            raise ProviderUnavailableError("Connection error while downloading from Copernicus.") from exc

        if not content:
            raise SceneDownloadError("Downloaded scene file was empty.")

        path = storage.save(scene.product_id, f"{scene.product_id}.zip", content)
        return DownloadResult(file_path=path, size_bytes=len(content), content_type="application/zip")


def _build_filter(params: SearchParams) -> str:
    aoi = params.aoi
    # Coordinate order verified live: (west,south),(west,north),(east,north),
    # (east,south),(west,south) — closed ring, longitude first (x y).
    polygon = (
        f"POLYGON(({aoi.west} {aoi.south}, {aoi.west} {aoi.north}, "
        f"{aoi.east} {aoi.north}, {aoi.east} {aoi.south}, {aoi.west} {aoi.south}))"
    )
    start_iso = _start_of_day(params.start_date)
    end_iso = _start_of_day(params.end_date)
    return (
        f"Collection/Name eq '{COLLECTION}' and "
        f"OData.CSC.Intersects(area=geography'SRID=4326;{polygon}') and "
        f"ContentDate/Start gt {start_iso} and "
        f"ContentDate/Start lt {end_iso} and "
        f"Attributes/OData.CSC.DoubleAttribute/any(att:att/Name eq 'cloudCover' and "
        f"att/OData.CSC.DoubleAttribute/Value le {params.max_cloud_cover}) and "
        f"Attributes/OData.CSC.StringAttribute/any(att:att/Name eq 'processingLevel' and "
        f"att/OData.CSC.StringAttribute/Value eq '{PROCESSING_LEVEL}')"
    )


def _start_of_day(d: date) -> str:
    return datetime(d.year, d.month, d.day, tzinfo=timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")


def _to_candidate(product: dict) -> SceneCandidate:
    attrs = {a.get("Name"): a.get("Value") for a in product.get("Attributes", [])}

    platform_short = attrs.get("platformShortName")
    platform_serial = attrs.get("platformSerialIdentifier")
    platform = f"{platform_short}{platform_serial}" if platform_short and platform_serial else platform_short

    acquisition_dt = None
    content_date = product.get("ContentDate") or {}
    if content_date.get("Start"):
        try:
            acquisition_dt = datetime.fromisoformat(content_date["Start"].replace("Z", "+00:00"))
        except ValueError:
            acquisition_dt = None

    return SceneCandidate(
        product_id=product["Id"],
        name=product.get("Name", product["Id"]),
        collection=COLLECTION,
        platform=platform,
        instrument=attrs.get("instrumentShortName"),
        acquisition_datetime=acquisition_dt,
        cloud_cover=attrs.get("cloudCover"),
        footprint=product.get("GeoFootprint"),
        size_bytes=product.get("ContentLength"),
        source_url=f"{get_settings().copernicus_catalog_url}/Products({product['Id']})",
    )
