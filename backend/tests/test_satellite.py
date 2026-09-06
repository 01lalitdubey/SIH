"""Phase 5 tests — satellite data acquisition.

Every test here runs against FakeSatelliteProvider (see conftest.py's
autouse `_fake_satellite_provider` fixture) — no network call is made, and
none of these tests require real Copernicus credentials. The one thing NOT
covered here is a real Copernicus round-trip; that's exercised separately
and only when credentials are actually configured (see
backend/README.md "Live Copernicus verification").

Background tasks run synchronously within TestClient's request/response
cycle (see test_api.py's module docstring), so a job created by POST
/process is already in its terminal state by the time the call returns.
"""

import pytest

from app.services.satellite.base import AOIPolygon, SearchParams
from app.services.satellite.exceptions import (
    InvalidAOIError,
    InvalidCloudCoverError,
    InvalidDateRangeError,
)
from app.services.satellite.service import build_search_params

VALID_AOI = {"north": 25.7, "south": 20.6, "east": 81.6, "west": 72.4}


def _create_aoi_job(client, aoi=None, **extra):
    payload = {"analysis_name": "Satellite Test", "scale_factor": 2, "aoi": aoi or VALID_AOI, **extra}
    return client.post("/api/v1/process", json=payload)


# --- Request-level validation (Pydantic, 422) -------------------------------


def test_aoi_rejects_inverted_bounds(client):
    resp = _create_aoi_job(client, aoi={"north": 20.6, "south": 25.7, "east": 81.6, "west": 72.4})
    assert resp.status_code == 422


def test_aoi_rejects_out_of_range_latitude(client):
    resp = _create_aoi_job(client, aoi={"north": 200, "south": 20.6, "east": 81.6, "west": 72.4})
    assert resp.status_code == 422


def test_date_range_rejects_start_after_end(client):
    resp = _create_aoi_job(client, start_date="2026-09-01", end_date="2026-08-01")
    assert resp.status_code == 422


def test_cloud_cover_rejects_out_of_range(client):
    resp = _create_aoi_job(client, max_cloud_cover=150)
    assert resp.status_code == 422


# --- Service-level validation (defends against malformed stored JSON) ------


def test_service_rejects_missing_aoi_keys():
    with pytest.raises(InvalidAOIError):
        build_search_params({"north": 1, "south": 0})  # missing east/west


def test_service_rejects_inverted_bounds_defensively():
    with pytest.raises(InvalidAOIError):
        build_search_params({"north": 0, "south": 1, "east": 1, "west": 0})


def test_service_rejects_bad_date_string():
    with pytest.raises(InvalidDateRangeError):
        build_search_params({**VALID_AOI, "search": {"start_date": "not-a-date"}})


def test_service_rejects_oversized_search_window():
    with pytest.raises(InvalidDateRangeError):
        build_search_params(
            {**VALID_AOI, "search": {"start_date": "2020-01-01", "end_date": "2026-01-01"}}
        )


def test_service_rejects_bad_cloud_cover():
    with pytest.raises(InvalidCloudCoverError):
        build_search_params({**VALID_AOI, "search": {"max_cloud_cover": -5}})


def test_service_applies_defaults_when_omitted():
    params = build_search_params(VALID_AOI)
    assert params.max_cloud_cover == 20.0
    assert (params.end_date - params.start_date).days == 30


# --- Provider failure modes --------------------------------------------------


def test_missing_credentials_fails_job_clearly(client, _fake_satellite_provider):
    _fake_satellite_provider.fail_auth_missing_credentials = True
    job = _create_aoi_job(client).json()

    status_resp = client.get(f"/api/v1/process/{job['job_id']}").json()
    assert status_resp["status"] == "failed"
    assert "credentials" in status_resp["error_message"].lower()
    assert status_resp["satellite_scene"] is None  # never got far enough to select one


def test_rejected_credentials_fails_job(client, _fake_satellite_provider):
    _fake_satellite_provider.fail_auth_rejected = True
    job = _create_aoi_job(client).json()

    status_resp = client.get(f"/api/v1/process/{job['job_id']}").json()
    assert status_resp["status"] == "failed"
    assert "rejected" in status_resp["error_message"].lower()


def test_search_unavailable_fails_job(client, _fake_satellite_provider):
    _fake_satellite_provider.fail_search_unavailable = True
    job = _create_aoi_job(client).json()

    status_resp = client.get(f"/api/v1/process/{job['job_id']}").json()
    assert status_resp["status"] == "failed"
    assert "unavailable" in status_resp["error_message"].lower()


def test_no_scenes_found_fails_job(client, _fake_satellite_provider):
    _fake_satellite_provider.fail_search_no_scenes = True
    job = _create_aoi_job(client).json()

    status_resp = client.get(f"/api/v1/process/{job['job_id']}").json()
    assert status_resp["status"] == "failed"
    assert "no scenes" in status_resp["error_message"].lower()
    assert status_resp["satellite_scene"] is None


def test_download_failure_fails_job_but_keeps_scene_metadata(client, _fake_satellite_provider):
    _fake_satellite_provider.fail_download = True
    job = _create_aoi_job(client).json()

    status_resp = client.get(f"/api/v1/process/{job['job_id']}").json()
    assert status_resp["status"] == "failed"
    # The scene WAS identified (real metadata persisted) even though the
    # download itself failed — a failed download must never look like a
    # successful job, but the identified scene shouldn't be thrown away.
    scene = status_resp["satellite_scene"]
    assert scene is not None
    assert scene["download_status"] == "failed"
    assert scene["product_id"] in ("fake-scene-clear", "fake-scene-cloudy")

    # And a failed job must never expose a result.
    result_resp = client.get(f"/api/v1/results/{job['job_id']}")
    assert result_resp.status_code == 404


def test_oversized_scene_declines_download_without_faking_success(client, _fake_satellite_provider):
    _fake_satellite_provider.oversized_scene_bytes = 500 * 1024 * 1024  # 500MB > cap
    job = _create_aoi_job(client).json()

    status_resp = client.get(f"/api/v1/process/{job['job_id']}").json()
    assert status_resp["status"] == "failed"
    assert status_resp["satellite_scene"]["download_status"] == "failed"


# --- Happy path: search -> ranking -> download -> persistence --------------


def test_full_satellite_pipeline_selects_clearest_scene_and_completes(client):
    resp = _create_aoi_job(client)
    assert resp.status_code == 201
    job = resp.json()

    status_resp = client.get(f"/api/v1/process/{job['job_id']}").json()
    assert status_resp["status"] == "completed"

    scene = status_resp["satellite_scene"]
    assert scene is not None
    # FakeSatelliteProvider offers a 5%-cloud and a 45%-cloud candidate over
    # the same AOI/date — select_best_scene's real ranking (base.py) must
    # deterministically prefer the clearer one.
    assert scene["product_id"] == "fake-scene-clear"
    assert scene["cloud_cover"] == 5.0
    assert scene["collection"] == "SENTINEL-2"
    assert scene["platform"] == "Sentinel-2X"
    assert scene["instrument"] == "MSI"
    assert scene["download_status"] == "completed"

    # The mock processing pipeline still runs afterward, unmodified.
    result = client.get(f"/api/v1/results/{job['job_id']}").json()
    assert result["is_mock"] is True


def test_satellite_scene_reachable_via_dedicated_endpoint(client):
    job = _create_aoi_job(client).json()
    status_resp = client.get(f"/api/v1/process/{job['job_id']}").json()
    scene_id = status_resp["satellite_scene"]["id"]

    scene_resp = client.get(f"/api/v1/satellite/scenes/{scene_id}")
    assert scene_resp.status_code == 200
    assert scene_resp.json()["product_id"] == "fake-scene-clear"

    file_resp = client.get(f"/api/v1/satellite/scenes/{scene_id}/file")
    assert file_resp.status_code == 200
    assert file_resp.content == b"FAKE-QUICKLOOK-BYTES"


def test_image_driven_job_never_touches_satellite_service(client, sample_image_bytes):
    """Regression guard: an image-only job must behave exactly as it did in
    Phase 4 — no satellite_scene, no satellite-related delay/failure."""
    image = client.post(
        "/api/v1/images/upload",
        files={"file": ("plain.jpg", sample_image_bytes, "image/jpeg")},
    ).json()
    job = client.post(
        "/api/v1/process",
        json={"image_id": image["id"], "analysis_name": "No AOI", "scale_factor": 2},
    ).json()

    status_resp = client.get(f"/api/v1/process/{job['job_id']}").json()
    assert status_resp["status"] == "completed"
    assert status_resp["satellite_scene"] is None


def test_ranking_prefers_higher_aoi_coverage_over_cloud_cover():
    """Direct unit test of BaseSatelliteProvider.select_best_scene's ranking,
    independent of the API — a scene whose footprint only partially covers
    the AOI should lose to a fully-covering scene even with more cloud."""
    from datetime import date, datetime, timezone

    from app.services.satellite.base import BaseSatelliteProvider, SceneCandidate

    class _Provider(BaseSatelliteProvider):
        def authenticate(self):
            pass

        def search_scenes(self, params):
            return []

        def download_scene(self, scene, storage):
            raise NotImplementedError

    aoi = AOIPolygon(north=10, south=0, east=10, west=0)
    params = SearchParams(
        aoi=aoi,
        start_date=date(2026, 1, 1),
        end_date=date(2026, 1, 31),
        max_cloud_cover=100,
    )
    full_coverage_cloudy = SceneCandidate(
        product_id="full",
        name="full",
        collection="SENTINEL-2",
        platform="Sentinel-2A",
        instrument="MSI",
        acquisition_datetime=datetime(2026, 1, 30, tzinfo=timezone.utc),
        cloud_cover=40.0,
        footprint={"type": "Polygon", "coordinates": [[[0, 0], [0, 10], [10, 10], [10, 0], [0, 0]]]},
        size_bytes=1,
        source_url=None,
    )
    partial_coverage_clear = SceneCandidate(
        product_id="partial",
        name="partial",
        collection="SENTINEL-2",
        platform="Sentinel-2A",
        instrument="MSI",
        acquisition_datetime=datetime(2026, 1, 30, tzinfo=timezone.utc),
        cloud_cover=2.0,
        footprint={"type": "Polygon", "coordinates": [[[0, 0], [0, 2], [2, 2], [2, 0], [0, 0]]]},
        size_bytes=1,
        source_url=None,
    )

    provider = _Provider()
    selected = provider.select_best_scene([partial_coverage_clear, full_coverage_cloudy], params)
    assert selected.product_id == "full"
