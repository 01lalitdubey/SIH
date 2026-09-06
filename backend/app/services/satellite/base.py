"""Provider-agnostic satellite abstraction.

    SatelliteService
          |
          v
    BaseSatelliteProvider (this module)
          |
          v
    CopernicusSatelliteProvider   <- CURRENT (Phase 5, this phase)
    <some other provider>         <- possible later, same interface

`SatelliteService` (services/satellite/service.py) depends only on this
interface, never on Copernicus specifics, so a second provider — or a fake
one for tests (services/satellite/fake.py) — is a drop-in replacement.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date, datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.services.satellite.storage import BaseSatelliteStorage


@dataclass(frozen=True)
class AOIPolygon:
    """A validated rectangular AOI. Bounds are kept (not just a geometry
    blob) because ranking (bounding-box coverage) and the OData query
    builder both need them directly."""

    north: float
    south: float
    east: float
    west: float

    def to_geojson(self) -> dict:
        ring = [
            [self.west, self.south],
            [self.west, self.north],
            [self.east, self.north],
            [self.east, self.south],
            [self.west, self.south],
        ]
        return {"type": "Polygon", "coordinates": [ring]}


@dataclass(frozen=True)
class SearchParams:
    aoi: AOIPolygon
    start_date: date
    end_date: date
    max_cloud_cover: float


@dataclass(frozen=True)
class SceneCandidate:
    """One product returned by a provider's search — enough to rank it and,
    if selected, describe + retrieve it. Not persisted directly; the chosen
    candidate is what SatelliteService turns into a SatelliteScene row."""

    product_id: str
    name: str
    collection: str
    platform: str | None
    instrument: str | None
    acquisition_datetime: datetime | None
    cloud_cover: float | None
    footprint: dict | None  # GeoJSON geometry
    size_bytes: int | None
    source_url: str | None


@dataclass(frozen=True)
class DownloadResult:
    file_path: str
    size_bytes: int
    content_type: str | None


class BaseSatelliteProvider(ABC):
    name: str = "base"

    @abstractmethod
    def authenticate(self) -> None:
        """Establish credentials for subsequent calls. Must raise
        MissingCredentialsError / AuthenticationError / ProviderUnavailableError
        rather than let a raw HTTP exception escape."""
        raise NotImplementedError

    @abstractmethod
    def search_scenes(self, params: SearchParams) -> list[SceneCandidate]:
        raise NotImplementedError

    @abstractmethod
    def download_scene(
        self, scene: SceneCandidate, storage: "BaseSatelliteStorage"
    ) -> DownloadResult:
        raise NotImplementedError

    def select_best_scene(
        self, candidates: list[SceneCandidate], params: SearchParams
    ) -> SceneCandidate:
        """Deterministic ranking shared by every provider (fake providers get
        the same real ranking logic real jobs do, not a stub).

        Ranking key, ascending (first wins):
          1. AOI coverage — fraction of the AOI bounding box covered by the
             scene's footprint bounding box, descending (approximated with
             plain bbox overlap; no shapely/GDAL dependency for this phase).
          2. Cloud cover, ascending (unknown cloud cover sorts last).
          3. Distance in days between the scene's acquisition date and the
             requested end_date, ascending (prefers the most recent scene
             inside the window).

        Never random — the same candidate list always ranks the same way.
        """
        if not candidates:
            raise ValueError("select_best_scene called with an empty candidate list")

        def rank_key(candidate: SceneCandidate) -> tuple[float, float, int]:
            coverage = _aoi_coverage_ratio(candidate.footprint, params.aoi)
            cloud = candidate.cloud_cover if candidate.cloud_cover is not None else 100.0
            if candidate.acquisition_datetime is not None:
                day_distance = abs((candidate.acquisition_datetime.date() - params.end_date).days)
            else:
                day_distance = 10_000
            return (-round(coverage, 4), cloud, day_distance)

        return sorted(candidates, key=rank_key)[0]

    def get_scene_metadata(self, scene: SceneCandidate) -> dict:
        return {
            "product_id": scene.product_id,
            "name": scene.name,
            "collection": scene.collection,
            "platform": scene.platform,
            "instrument": scene.instrument,
            "acquisition_datetime": scene.acquisition_datetime.isoformat()
            if scene.acquisition_datetime
            else None,
            "cloud_cover": scene.cloud_cover,
            "size_bytes": scene.size_bytes,
        }


def _aoi_coverage_ratio(footprint: dict | None, aoi: AOIPolygon) -> float:
    """Fraction (0..1) of the AOI's bounding box overlapped by the
    footprint's bounding box. A pure bbox approximation — real polygon
    intersection (shapely/GDAL) is Phase 7 territory, not needed here since
    it only affects *ranking order* among already-intersecting candidates
    (the search query itself already filters to scenes that intersect the
    AOI at all)."""
    if not footprint or footprint.get("type") != "Polygon":
        return 0.0
    coords = footprint.get("coordinates")
    if not coords or not coords[0]:
        return 0.0

    lons = [pt[0] for pt in coords[0]]
    lats = [pt[1] for pt in coords[0]]
    f_west, f_east = min(lons), max(lons)
    f_south, f_north = min(lats), max(lats)

    overlap_west = max(aoi.west, f_west)
    overlap_east = min(aoi.east, f_east)
    overlap_south = max(aoi.south, f_south)
    overlap_north = min(aoi.north, f_north)

    if overlap_east <= overlap_west or overlap_north <= overlap_south:
        return 0.0

    overlap_area = (overlap_east - overlap_west) * (overlap_north - overlap_south)
    aoi_area = (aoi.east - aoi.west) * (aoi.north - aoi.south)
    if aoi_area <= 0:
        return 0.0
    return min(overlap_area / aoi_area, 1.0)
