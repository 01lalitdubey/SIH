"""Deterministic in-memory provider used only by the test suite.

Implements the exact same BaseSatelliteProvider interface as
CopernicusSatelliteProvider, so tests exercise the real SatelliteService
orchestration (validation, ranking, persistence, error propagation)
without ever making a network call. Each failure mode below mirrors a
specific real Copernicus failure (see exceptions.py), so tests can select
one deliberately by constructing the fake with that mode.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

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


@dataclass
class FakeSatelliteProvider(BaseSatelliteProvider):
    name: str = "fake"

    # Test-selectable failure injection — None means "succeed normally".
    fail_auth_missing_credentials: bool = False
    fail_auth_rejected: bool = False
    fail_search_unavailable: bool = False
    fail_search_no_scenes: bool = False
    fail_download: bool = False
    fail_download_unavailable: bool = False
    oversized_scene_bytes: int | None = None

    authenticated: bool = False

    def authenticate(self) -> None:
        if self.fail_auth_missing_credentials:
            raise MissingCredentialsError("Fake: no credentials configured.")
        if self.fail_auth_rejected:
            raise AuthenticationError("Fake: credentials rejected.")
        self.authenticated = True

    def search_scenes(self, params: SearchParams) -> list[SceneCandidate]:
        if self.fail_search_unavailable:
            raise ProviderUnavailableError("Fake: catalog temporarily unavailable.")
        if self.fail_search_no_scenes:
            raise NoScenesFoundError("Fake: no scenes matched.")

        base_dt = datetime.combine(params.end_date, datetime.min.time(), tzinfo=timezone.utc)
        size = self.oversized_scene_bytes or 2_000_000  # ~2MB fake quicklook-sized payload

        # Two candidates so ranking is genuinely exercised, not a 1-item list.
        return [
            SceneCandidate(
                product_id="fake-scene-clear",
                name="S2X_MSIL2A_FAKE_CLEAR",
                collection="SENTINEL-2",
                platform="Sentinel-2X",
                instrument="MSI",
                acquisition_datetime=base_dt - timedelta(days=1),
                cloud_cover=5.0,
                footprint=params.aoi.to_geojson(),
                size_bytes=size,
                source_url="https://example.invalid/fake-scene-clear",
            ),
            SceneCandidate(
                product_id="fake-scene-cloudy",
                name="S2X_MSIL2A_FAKE_CLOUDY",
                collection="SENTINEL-2",
                platform="Sentinel-2X",
                instrument="MSI",
                acquisition_datetime=base_dt,
                cloud_cover=45.0,
                footprint=params.aoi.to_geojson(),
                size_bytes=size,
                source_url="https://example.invalid/fake-scene-cloudy",
            ),
        ]

    def download_scene(self, scene: SceneCandidate, storage: BaseSatelliteStorage) -> DownloadResult:
        if self.fail_download_unavailable:
            raise ProviderUnavailableError("Fake: download service unavailable.")
        if self.fail_download:
            raise SceneDownloadError("Fake: download failed.")
        if scene.size_bytes and scene.size_bytes > 200 * 1024 * 1024:
            raise SceneDownloadError(
                f"Fake: scene '{scene.name}' exceeds the retrieval cap; metadata only."
            )

        content = b"FAKE-QUICKLOOK-BYTES"
        path = storage.save(scene.product_id, f"{scene.product_id}.jpg", content)
        return DownloadResult(file_path=path, size_bytes=len(content), content_type="image/jpeg")
