"""GEESatelliteProvider tests — Phase 6.3. Every test here runs against a
mocked `ee` module (via `provider._ee` monkeypatched) or mocked HTTP
responses — no real Google Earth Engine credentials are used or required.
See backend/README.md "Phase 6.3" for whether a real live GEE test was
actually executed this session, and why/why not.
"""

import io
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock

import numpy as np
import pytest
import tifffile
from PIL import Image as PILImage

from app.core.config import get_settings
from app.services.satellite.base import AOIPolygon, SceneCandidate, SearchParams
from app.services.satellite.exceptions import (
    AuthenticationError,
    MissingCredentialsError,
    NoScenesFoundError,
    ProviderUnavailableError,
    SceneDownloadError,
)
from app.services.satellite.gee import (
    BANDS,
    COLLECTION,
    GEESatelliteProvider,
    _estimate_request_bytes,
    _reflectance_to_uint8_rgb,
    _to_candidate,
)
from app.services.satellite.storage import LocalSatelliteStorage


# Small enough (~5.5km x 5.5km) to stay under GEE's real 32MB synchronous
# getDownloadURL ceiling at 10m/pixel, 3 bands, uint16 — see
# _estimate_request_bytes / MAX_SYNC_DOWNLOAD_BYTES in gee.py. A separate,
# deliberately oversized AOI is used in test_download_scene_rejects_oversized_aoi.
VALID_AOI = AOIPolygon(north=21.85, south=21.80, east=88.85, west=88.80)
VALID_PARAMS = SearchParams(
    aoi=VALID_AOI, start_date=date(2023, 6, 1), end_date=date(2023, 8, 1), max_cloud_cover=60.0
)


def _mock_ee() -> MagicMock:
    mock_ee = MagicMock()
    mock_ee.EEException = RuntimeError  # a real exception class, so `except ee.EEException` stays valid
    return mock_ee


def _authenticated_provider(monkeypatch, mock_ee) -> GEESatelliteProvider:
    provider = GEESatelliteProvider()
    provider._initialized = True  # skip authenticate() — this exercises search/download logic only
    monkeypatch.setattr(provider, "_ee", lambda: mock_ee)
    return provider


def _mock_collection(mock_ee, features):
    collection = MagicMock()
    mock_ee.ImageCollection.return_value = collection
    collection.filterBounds.return_value = collection
    collection.filterDate.return_value = collection
    collection.filter.return_value = collection
    collection.limit.return_value = collection
    collection.getInfo.return_value = {"features": features}
    return collection


def _fake_feature(cloud=5.9, index="20230605T042709_20230605T043705_T45QYE"):
    return {
        "type": "Image",
        "id": f"COPERNICUS/S2_SR_HARMONIZED/{index}",
        "properties": {
            "system:index": index,
            "system:time_start": 1685939229000,  # real epoch millis for 2023-06-05T04:27:09Z
            "CLOUDY_PIXEL_PERCENTAGE": cloud,
            "SPACECRAFT_NAME": "Sentinel-2B",
            "PRODUCT_ID": "S2B_MSIL2A_20230605T042709_N0510_R133_T45QYE_20240909T060835",
        },
    }


def _fake_scene(footprint=None) -> SceneCandidate:
    return SceneCandidate(
        product_id="COPERNICUS/S2_SR_HARMONIZED/20230605T042709_20230605T043705_T45QYE",
        name="S2B_MSIL2A_test",
        collection="SENTINEL-2",
        platform="Sentinel-2B",
        instrument="MSI",
        acquisition_datetime=None,
        cloud_cover=5.9,
        footprint=footprint or VALID_AOI.to_geojson(),
        size_bytes=None,
        source_url=None,
    )


def _real_tiff_bytes(width=32, height=32, reflectance_max=4500) -> bytes:
    """A genuine, decodable 3-band uint16 GeoTIFF — the same shape/dtype
    ee.Image.getDownloadURL(format='GEO_TIFF') would actually return."""
    arr = (np.random.rand(len(BANDS), height, width) * reflectance_max).astype(np.uint16)
    buf = io.BytesIO()
    tifffile.imwrite(buf, arr, photometric="rgb")
    return buf.getvalue()


class _FakeHTTPResponse:
    def __init__(self, status_code=200, content=b"", text=""):
        self.status_code = status_code
        self.content = content
        self.text = text


# --- Provider selection / configuration -------------------------------------


def test_satellite_provider_selects_gee(monkeypatch):
    monkeypatch.setattr(get_settings(), "satellite_provider", "gee")
    from app.services.satellite import service

    provider = service._build_provider()
    assert isinstance(provider, GEESatelliteProvider)
    assert provider.name == "gee"


def test_satellite_provider_rejects_unknown_value(monkeypatch):
    monkeypatch.setattr(get_settings(), "satellite_provider", "not_a_real_provider")
    from app.services.satellite import service

    with pytest.raises(ValueError, match="Unknown SATELLITE_PROVIDER"):
        service._build_provider()


def test_bands_are_rgb_only_no_nir():
    """Item 9/10: exactly B4/B3/B2, no B8/NIR — the trained Phase 6
    checkpoint has 3 input channels; a 4th would break compatibility."""
    assert BANDS == ["B4", "B3", "B2"]
    assert "B8" not in BANDS
    assert len(BANDS) == 3


def test_collection_is_sentinel2_sr_harmonized():
    assert COLLECTION == "COPERNICUS/S2_SR_HARMONIZED"


# --- Authentication -----------------------------------------------------


def test_missing_gee_credentials_raises_clearly(monkeypatch):
    monkeypatch.setattr(get_settings(), "gee_project_id", None)
    monkeypatch.setattr(get_settings(), "gee_service_account_email", None)
    monkeypatch.setattr(get_settings(), "gee_service_account_key_path", None)
    provider = GEESatelliteProvider()
    with pytest.raises(MissingCredentialsError, match="not configured"):
        provider.authenticate()


def test_missing_gee_project_raises_clearly(monkeypatch, tmp_path):
    key_file = tmp_path / "key.json"
    key_file.write_text("{}")
    monkeypatch.setattr(get_settings(), "gee_project_id", None)
    monkeypatch.setattr(get_settings(), "gee_service_account_email", "svc@example.iam.gserviceaccount.com")
    monkeypatch.setattr(get_settings(), "gee_service_account_key_path", str(key_file))
    provider = GEESatelliteProvider()
    with pytest.raises(MissingCredentialsError):
        provider.authenticate()


def test_missing_key_file_raises_clearly(monkeypatch, tmp_path):
    monkeypatch.setattr(get_settings(), "gee_project_id", "my-project")
    monkeypatch.setattr(get_settings(), "gee_service_account_email", "svc@example.iam.gserviceaccount.com")
    monkeypatch.setattr(get_settings(), "gee_service_account_key_path", str(tmp_path / "missing.json"))
    provider = GEESatelliteProvider()
    with pytest.raises(MissingCredentialsError, match="not found"):
        provider.authenticate()


def test_authenticate_initializes_ee_with_service_account(monkeypatch, tmp_path):
    key_file = tmp_path / "key.json"
    key_file.write_text("{}")
    monkeypatch.setattr(get_settings(), "gee_project_id", "my-project")
    monkeypatch.setattr(get_settings(), "gee_service_account_email", "svc@example.iam.gserviceaccount.com")
    monkeypatch.setattr(get_settings(), "gee_service_account_key_path", str(key_file))

    provider = GEESatelliteProvider()
    mock_ee = _mock_ee()
    mock_ee.ServiceAccountCredentials.return_value = "FAKE_CREDENTIALS"
    monkeypatch.setattr(provider, "_ee", lambda: mock_ee)

    provider.authenticate()

    mock_ee.ServiceAccountCredentials.assert_called_once_with(
        email="svc@example.iam.gserviceaccount.com", key_file=str(key_file)
    )
    mock_ee.Initialize.assert_called_once_with("FAKE_CREDENTIALS", project="my-project")
    assert provider._initialized is True

    provider.authenticate()  # second call must not re-initialize
    mock_ee.Initialize.assert_called_once()


def test_authenticate_wraps_ee_failure(monkeypatch, tmp_path):
    key_file = tmp_path / "key.json"
    key_file.write_text("{}")
    monkeypatch.setattr(get_settings(), "gee_project_id", "my-project")
    monkeypatch.setattr(get_settings(), "gee_service_account_email", "svc@example.iam.gserviceaccount.com")
    monkeypatch.setattr(get_settings(), "gee_service_account_key_path", str(key_file))

    provider = GEESatelliteProvider()
    mock_ee = _mock_ee()
    mock_ee.Initialize.side_effect = RuntimeError("boom")
    monkeypatch.setattr(provider, "_ee", lambda: mock_ee)

    with pytest.raises(AuthenticationError, match="rejected"):
        provider.authenticate()


# --- Search -------------------------------------------------------------


def test_search_builds_correct_geometry_lon_lat_order(monkeypatch):
    mock_ee = _mock_ee()
    provider = _authenticated_provider(monkeypatch, mock_ee)
    _mock_collection(mock_ee, [_fake_feature()])

    provider.search_scenes(VALID_PARAMS)

    mock_ee.Geometry.Rectangle.assert_called_once_with(
        [VALID_AOI.west, VALID_AOI.south, VALID_AOI.east, VALID_AOI.north]
    )


def test_search_uses_sentinel2_sr_harmonized_collection(monkeypatch):
    mock_ee = _mock_ee()
    provider = _authenticated_provider(monkeypatch, mock_ee)
    _mock_collection(mock_ee, [_fake_feature()])

    provider.search_scenes(VALID_PARAMS)

    mock_ee.ImageCollection.assert_called_once_with(COLLECTION)


def test_search_filters_by_date_range(monkeypatch):
    mock_ee = _mock_ee()
    provider = _authenticated_provider(monkeypatch, mock_ee)
    collection = _mock_collection(mock_ee, [_fake_feature()])

    provider.search_scenes(VALID_PARAMS)

    collection.filterDate.assert_called_once_with("2023-06-01", "2023-08-01")


def test_search_filters_by_cloud_cover(monkeypatch):
    mock_ee = _mock_ee()
    provider = _authenticated_provider(monkeypatch, mock_ee)
    _mock_collection(mock_ee, [_fake_feature()])

    provider.search_scenes(VALID_PARAMS)

    mock_ee.Filter.lt.assert_called_once_with("CLOUDY_PIXEL_PERCENTAGE", 60.0)


def test_search_raises_no_scenes_found_when_empty(monkeypatch):
    mock_ee = _mock_ee()
    provider = _authenticated_provider(monkeypatch, mock_ee)
    _mock_collection(mock_ee, [])

    with pytest.raises(NoScenesFoundError):
        provider.search_scenes(VALID_PARAMS)


def test_search_wraps_ee_exception(monkeypatch):
    mock_ee = _mock_ee()
    provider = _authenticated_provider(monkeypatch, mock_ee)
    collection = _mock_collection(mock_ee, [])
    collection.getInfo.side_effect = mock_ee.EEException("quota exceeded")

    with pytest.raises(ProviderUnavailableError):
        provider.search_scenes(VALID_PARAMS)


def test_to_candidate_conversion():
    feature = _fake_feature()
    candidate = _to_candidate(feature, VALID_AOI)

    assert candidate.product_id == feature["id"]
    assert candidate.name == "S2B_MSIL2A_20230605T042709_N0510_R133_T45QYE_20240909T060835"
    assert candidate.collection == "SENTINEL-2"
    assert candidate.platform == "Sentinel-2B"
    assert candidate.instrument == "MSI"
    assert candidate.cloud_cover == 5.9
    assert candidate.acquisition_datetime is not None
    assert candidate.acquisition_datetime.year == 2023
    assert candidate.acquisition_datetime.month == 6
    assert candidate.acquisition_datetime.day == 5
    # Item 10 (footprint): the requested AOI, not a claimed verified scene
    # footprint — see gee.py's _to_candidate docstring.
    assert candidate.footprint == VALID_AOI.to_geojson()


# --- Download / normalization --------------------------------------------


def test_download_scene_normalizes_and_saves(monkeypatch, tmp_path):
    mock_ee = _mock_ee()
    provider = _authenticated_provider(monkeypatch, mock_ee)
    (
        mock_ee.Image.return_value.select.return_value.clip.return_value.getDownloadURL
    ).return_value = "https://example.invalid/download"

    monkeypatch.setattr(
        "app.services.satellite.gee.httpx.get",
        lambda *a, **k: _FakeHTTPResponse(200, _real_tiff_bytes()),
    )
    monkeypatch.setattr(get_settings(), "satellite_dir", str(tmp_path))

    result = provider.download_scene(_fake_scene(), LocalSatelliteStorage())

    assert Path(result.file_path).is_file()
    # The saved file must be exactly what SuperResolutionProcessor's
    # (unmodified) PIL-based loader can correctly consume — proven here,
    # not assumed. See gee.py's module docstring for the real test that
    # established why a raw uint16 pass-through would NOT be safe.
    with PILImage.open(result.file_path) as img:
        assert img.mode == "RGB"
        arr = np.array(img.convert("RGB"))
        assert arr.dtype == np.uint8
        assert arr.shape == (32, 32, 3)


def test_download_scene_rejects_oversized_aoi(monkeypatch):
    mock_ee = _mock_ee()
    provider = _authenticated_provider(monkeypatch, mock_ee)

    huge_footprint = {
        "type": "Polygon",
        "coordinates": [[[70.0, 10.0], [70.0, 15.0], [75.0, 15.0], [75.0, 10.0], [70.0, 10.0]]],
    }

    with pytest.raises(SceneDownloadError, match="too large"):
        provider.download_scene(_fake_scene(footprint=huge_footprint), LocalSatelliteStorage())

    mock_ee.Image.assert_not_called()  # must fail before ever calling Earth Engine


def test_estimate_request_bytes_against_gee_ceiling():
    small_aoi = AOIPolygon(north=21.81, south=21.80, east=88.81, west=88.80)  # ~0.01deg, ~1km
    assert _estimate_request_bytes(small_aoi) < 32 * 1024 * 1024

    huge_aoi = AOIPolygon(north=15.0, south=10.0, east=75.0, west=70.0)  # 5deg, ~500+km
    assert _estimate_request_bytes(huge_aoi) > 32 * 1024 * 1024


def test_download_scene_http_error(monkeypatch):
    mock_ee = _mock_ee()
    provider = _authenticated_provider(monkeypatch, mock_ee)
    (
        mock_ee.Image.return_value.select.return_value.clip.return_value.getDownloadURL
    ).return_value = "https://example.invalid/download"

    monkeypatch.setattr(
        "app.services.satellite.gee.httpx.get",
        lambda *a, **k: _FakeHTTPResponse(500, b"", "server error"),
    )

    with pytest.raises(ProviderUnavailableError):
        provider.download_scene(_fake_scene(), LocalSatelliteStorage())


def test_download_scene_rejects_oversized_response(monkeypatch):
    mock_ee = _mock_ee()
    provider = _authenticated_provider(monkeypatch, mock_ee)
    (
        mock_ee.Image.return_value.select.return_value.clip.return_value.getDownloadURL
    ).return_value = "https://example.invalid/download"

    monkeypatch.setattr(
        "app.services.satellite.gee.httpx.get",
        lambda *a, **k: _FakeHTTPResponse(200, b"x" * 1024),
    )
    monkeypatch.setattr(get_settings(), "satellite_max_download_mb", 0)

    with pytest.raises(SceneDownloadError, match="retrieval cap"):
        provider.download_scene(_fake_scene(), LocalSatelliteStorage())


def test_download_scene_rejects_empty_response(monkeypatch):
    mock_ee = _mock_ee()
    provider = _authenticated_provider(monkeypatch, mock_ee)
    (
        mock_ee.Image.return_value.select.return_value.clip.return_value.getDownloadURL
    ).return_value = "https://example.invalid/download"

    monkeypatch.setattr(
        "app.services.satellite.gee.httpx.get", lambda *a, **k: _FakeHTTPResponse(200, b"")
    )

    with pytest.raises(SceneDownloadError, match="empty"):
        provider.download_scene(_fake_scene(), LocalSatelliteStorage())


def test_download_scene_rejects_undecodable_content(monkeypatch):
    mock_ee = _mock_ee()
    provider = _authenticated_provider(monkeypatch, mock_ee)
    (
        mock_ee.Image.return_value.select.return_value.clip.return_value.getDownloadURL
    ).return_value = "https://example.invalid/download"

    monkeypatch.setattr(
        "app.services.satellite.gee.httpx.get",
        lambda *a, **k: _FakeHTTPResponse(200, b"not a real tiff"),
    )

    with pytest.raises(SceneDownloadError, match="could not be decoded"):
        provider.download_scene(_fake_scene(), LocalSatelliteStorage())


# --- Reflectance normalization (the RGB compatibility contract) -------------


def test_reflectance_normalization_matches_documented_scale():
    raw = np.zeros((3, 4, 4), dtype=np.uint16)
    raw[0] = 10000  # Red at full scale
    raw[1] = 5000  # Green at half scale
    raw[2] = 0  # Blue at zero
    result = _reflectance_to_uint8_rgb(raw)

    assert result.shape == (4, 4, 3)
    assert result.dtype == np.uint8
    assert result[0, 0, 0] == 255
    assert 120 <= result[0, 0, 1] <= 130
    assert result[0, 0, 2] == 0


def test_reflectance_normalization_clips_over_scale_values():
    # Real S2 SR values occasionally exceed 10000 slightly — must clip, not overflow/wrap.
    raw = np.full((3, 2, 2), 15000, dtype=np.uint16)
    result = _reflectance_to_uint8_rgb(raw)
    assert result.max() == 255
    assert result.min() == 255


def test_reflectance_handles_band_first_and_band_last_shapes():
    band_first = (np.random.rand(3, 8, 8) * 10000).astype(np.uint16)
    band_last = band_first.transpose(1, 2, 0)
    assert np.array_equal(_reflectance_to_uint8_rgb(band_first), _reflectance_to_uint8_rgb(band_last))


def test_reflectance_rejects_wrong_band_count():
    wrong_shape = np.zeros((4, 4, 4), dtype=np.uint16)  # 4 bands, not 3 — must never reach EDSRLite
    with pytest.raises(ValueError, match="3-band"):
        _reflectance_to_uint8_rgb(wrong_shape)


# --- End-to-end wiring (item 16: AOI actually invokes the configured provider) --


def test_aoi_job_invokes_configured_gee_provider(client, monkeypatch, tmp_path):
    from app.services.satellite import service as satellite_service

    mock_ee = _mock_ee()
    provider = GEESatelliteProvider()
    provider._initialized = True
    monkeypatch.setattr(provider, "_ee", lambda: mock_ee)
    monkeypatch.setattr(satellite_service, "_provider", provider)
    monkeypatch.setattr(get_settings(), "satellite_dir", str(tmp_path))

    _mock_collection(mock_ee, [_fake_feature()])
    (
        mock_ee.Image.return_value.select.return_value.clip.return_value.getDownloadURL
    ).return_value = "https://example.invalid/download"
    monkeypatch.setattr(
        "app.services.satellite.gee.httpx.get",
        lambda *a, **k: _FakeHTTPResponse(200, _real_tiff_bytes()),
    )

    resp = client.post(
        "/api/v1/process",
        json={
            "analysis_name": "GEE AOI test",
            "scale_factor": 2,
            "aoi": {"north": 21.85, "south": 21.80, "east": 88.85, "west": 88.80},
        },
    )
    job = resp.json()

    status = client.get(f"/api/v1/process/{job['job_id']}").json()
    assert status["satellite_scene"]["provider"] == "gee"
    assert status["satellite_scene"]["download_status"] == "completed"
    mock_ee.ImageCollection.assert_called_once_with(COLLECTION)
