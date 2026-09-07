"""SuperResolutionProcessor integration tests — run directly against the
processor (not the full HTTP stack), using the same in-memory SQLite
session the rest of the suite uses (see conftest.py). No network, no real
Copernicus/SEN2VENuS access, no GPU required: the "real" checkpoint used
here is trained in-process on tiny synthetic tensors in under a second
(a TRAINING SMOKE TEST checkpoint, not a claim of satellite training —
see test_ai_training_smoke.py), purely so SuperResolutionProcessor has a
structurally real checkpoint to load and run real tensor inference against.
"""

import uuid

import numpy as np
import pytest

torch = pytest.importorskip("torch")

from PIL import Image as PILImage  # noqa: E402

from app.core import database as db_module  # noqa: E402
from app.core.config import get_settings  # noqa: E402
from app.models.image import Image  # noqa: E402
from app.models.processing_job import JobStatus, ProcessingJob  # noqa: E402
from app.services import processing_service  # noqa: E402
from app.services.processors.mock_processor import MockProcessor  # noqa: E402
from app.services.processors.super_resolution_processor import SuperResolutionProcessor  # noqa: E402


@pytest.fixture
def trained_checkpoint(tmp_path):
    """A real (tiny, synthetic-trained) checkpoint — see module docstring."""
    from ai.training.train import TrainingConfig, run_training

    config = TrainingConfig(
        dataset="synthetic",
        epochs=1,
        batch_size=4,
        num_channels=3,
        num_features=8,
        num_res_blocks=1,
        scale_factor=2,
        max_train_samples=8,
        max_val_samples=4,
        checkpoint_name="test_edsr.pt",
    )
    import ai.training.train as train_module

    original_dir = train_module.CHECKPOINT_DIR
    train_module.CHECKPOINT_DIR = tmp_path
    try:
        run_training(config)
    finally:
        train_module.CHECKPOINT_DIR = original_dir
    return tmp_path / "test_edsr.pt"


def _make_image_job(db_session, tmp_path, scale_factor=2, size=(16, 16)) -> ProcessingJob:
    image_path = tmp_path / "input.png"
    PILImage.new("RGB", size, color=(80, 120, 160)).save(image_path)

    image = Image(
        filename="input.png",
        stored_filename=f"{uuid.uuid4().hex}.png",
        file_path=str(image_path),
        file_type="image/png",
        file_size=image_path.stat().st_size,
        width=size[0],
        height=size[1],
    )
    db_session.add(image)
    db_session.commit()
    db_session.refresh(image)

    job = ProcessingJob(
        image_id=image.id,
        analysis_name="SR processor test",
        scale_factor=scale_factor,
        status=JobStatus.QUEUED,
        progress=0,
    )
    db_session.add(job)
    db_session.commit()
    db_session.refresh(job)
    return job


def test_missing_checkpoint_fails_job_clearly(monkeypatch, tmp_path):
    monkeypatch.setattr(get_settings(), "sr_checkpoint_path", str(tmp_path / "missing.pt"))
    processor = SuperResolutionProcessor()

    session = db_module.SessionLocal()
    try:
        job = _make_image_job(session, tmp_path)
        processor.run(job.id)
        session.refresh(job)
        assert job.status == JobStatus.FAILED
        assert "not available" in job.error_message.lower()
    finally:
        session.close()


def test_real_inference_produces_real_result(monkeypatch, tmp_path, trained_checkpoint):
    monkeypatch.setattr(get_settings(), "sr_checkpoint_path", str(trained_checkpoint))
    processor = SuperResolutionProcessor()
    assert processor._engine is not None  # real checkpoint loaded, not deferred-error state

    session = db_module.SessionLocal()
    try:
        job = _make_image_job(session, tmp_path, scale_factor=2, size=(16, 16))
        processor.run(job.id)
        session.refresh(job)

        assert job.status == JobStatus.COMPLETED
        assert job.progress == 100

        from app.services import result_service

        result = result_service.get_result_by_job(session, job.id)
        assert result is not None
        assert result.is_mock is False
        assert result.model_name == "edsr_satellite"
        assert result.device in ("cpu", "cuda")
        # No ground truth exists for real inference — never fabricated.
        assert result.metrics_available is False
        assert result.psnr is None
        assert result.ssim is None
        assert result.lpips is None
        # 16x16 input, 2x model -> 32x32 output, actually produced.
        assert result.output_width == 32
        assert result.output_height == 32

        from pathlib import Path

        output_path = Path(result.output_path)
        assert output_path.is_file()
        with PILImage.open(output_path) as out_img:
            assert out_img.size == (32, 32)
    finally:
        session.close()


def test_scale_factor_mismatch_fails_job_clearly(monkeypatch, tmp_path, trained_checkpoint):
    monkeypatch.setattr(get_settings(), "sr_checkpoint_path", str(trained_checkpoint))
    processor = SuperResolutionProcessor()

    session = db_module.SessionLocal()
    try:
        # trained_checkpoint is a 2x model; request 4x.
        job = _make_image_job(session, tmp_path, scale_factor=4)
        processor.run(job.id)
        session.refresh(job)
        assert job.status == JobStatus.FAILED
        assert "2x" in job.error_message and "4x" in job.error_message
    finally:
        session.close()


def test_no_input_imagery_fails_job_clearly(monkeypatch, tmp_path, trained_checkpoint):
    monkeypatch.setattr(get_settings(), "sr_checkpoint_path", str(trained_checkpoint))
    processor = SuperResolutionProcessor()

    session = db_module.SessionLocal()
    try:
        # AOI-driven job with no satellite scene resolved (aoi_geometry set
        # but no SatelliteScene row) — mirrors a job with nothing to infer on.
        job = ProcessingJob(
            image_id=None,
            analysis_name="No input",
            scale_factor=2,
            aoi_geometry={"north": 1, "south": 0, "east": 1, "west": 0},
            status=JobStatus.QUEUED,
            progress=0,
        )
        session.add(job)
        session.commit()
        session.refresh(job)

        processor.run(job.id)
        session.refresh(job)
        assert job.status == JobStatus.FAILED
        assert "no input imagery" in job.error_message.lower()
    finally:
        session.close()


def test_processor_mode_selects_mock_by_default(monkeypatch):
    monkeypatch.setattr(get_settings(), "processor_mode", "mock")
    assert isinstance(processing_service._build_processor(), MockProcessor)


def test_processor_mode_selects_super_resolution(monkeypatch, trained_checkpoint):
    monkeypatch.setattr(get_settings(), "processor_mode", "super_resolution")
    monkeypatch.setattr(get_settings(), "sr_checkpoint_path", str(trained_checkpoint))
    processor = processing_service._build_processor()
    assert isinstance(processor, SuperResolutionProcessor)


def test_processor_mode_rejects_unknown_value(monkeypatch):
    monkeypatch.setattr(get_settings(), "processor_mode", "not_a_real_mode")
    with pytest.raises(ValueError, match="Unknown PROCESSOR_MODE"):
        processing_service._build_processor()


def test_processor_status_reports_mock(monkeypatch):
    monkeypatch.setattr(get_settings(), "processor_mode", "mock")
    status = processing_service.get_processor_status(MockProcessor())
    assert status == {
        "processor_mode": "mock",
        "is_mock": True,
        "processor_ready": True,
        "model_name": None,
        "model_version": None,
        "device": None,
        "scale_factor": None,
        "processor_error": None,
    }


def test_processor_status_reports_real_ready_state(monkeypatch, trained_checkpoint):
    monkeypatch.setattr(get_settings(), "processor_mode", "super_resolution")
    monkeypatch.setattr(get_settings(), "sr_checkpoint_path", str(trained_checkpoint))
    processor = SuperResolutionProcessor()

    status = processing_service.get_processor_status(processor)
    assert status["processor_mode"] == "super_resolution"
    assert status["is_mock"] is False
    assert status["processor_ready"] is True
    assert status["model_name"] == "edsr_satellite"
    assert status["scale_factor"] == 2
    assert status["device"] in ("cpu", "cuda")
    assert status["processor_error"] is None


def test_processor_status_reports_not_ready_when_checkpoint_missing(monkeypatch, tmp_path):
    monkeypatch.setattr(get_settings(), "processor_mode", "super_resolution")
    monkeypatch.setattr(get_settings(), "sr_checkpoint_path", str(tmp_path / "missing.pt"))
    processor = SuperResolutionProcessor()

    status = processing_service.get_processor_status(processor)
    assert status["is_mock"] is False
    assert status["processor_ready"] is False
    assert status["model_name"] is None
    assert status["scale_factor"] is None
    assert status["processor_error"] is not None


def test_super_resolution_never_silently_falls_back_to_mock(monkeypatch, tmp_path):
    """The core anti-fabrication rule: a broken real-mode configuration
    must fail the job, never quietly produce a MockProcessor-style result
    while claiming to be the real pipeline."""
    monkeypatch.setattr(get_settings(), "sr_checkpoint_path", str(tmp_path / "missing.pt"))
    processor = SuperResolutionProcessor()

    session = db_module.SessionLocal()
    try:
        job = _make_image_job(session, tmp_path)
        processor.run(job.id)
        session.refresh(job)

        from app.services import result_service

        assert job.status == JobStatus.FAILED
        assert result_service.get_result_by_job(session, job.id) is None
    finally:
        session.close()


def test_corrupt_input_image_fails_job_clearly(monkeypatch, tmp_path, trained_checkpoint):
    """Phase 6.2: a real Sentinel-2 quicklook (or any other unreadable file)
    must fail the job with a clear message, never crash the background task
    uncaught and leave the job stuck in 'processing' forever."""
    monkeypatch.setattr(get_settings(), "sr_checkpoint_path", str(trained_checkpoint))
    processor = SuperResolutionProcessor()

    bad_path = tmp_path / "not_really_an_image.jpg"
    bad_path.write_bytes(b"FAKE-QUICKLOOK-BYTES")  # same stub content FakeSatelliteProvider writes

    image = Image(
        filename="not_really_an_image.jpg",
        stored_filename=f"{uuid.uuid4().hex}.jpg",
        file_path=str(bad_path),
        file_type="image/jpeg",
        file_size=bad_path.stat().st_size,
        width=1,
        height=1,
    )
    session = db_module.SessionLocal()
    try:
        session.add(image)
        session.commit()
        session.refresh(image)

        job = ProcessingJob(
            image_id=image.id,
            analysis_name="Corrupt input test",
            scale_factor=2,
            status=JobStatus.QUEUED,
            progress=0,
        )
        session.add(job)
        session.commit()
        session.refresh(job)

        processor.run(job.id)
        session.refresh(job)

        assert job.status == JobStatus.FAILED
        assert "ai inference failed" in job.error_message.lower()
    finally:
        session.close()


def test_gee_normalized_output_is_compatible_with_super_resolution_processor(
    monkeypatch, tmp_path, trained_checkpoint
):
    """Phase 6.3: proves — empirically, not just by comment — that a real
    Sentinel-2 SR reflectance array, run through GEESatelliteProvider's own
    normalization (app/services/satellite/gee.py:_reflectance_to_uint8_rgb)
    and saved exactly as that provider saves it, is then correctly consumed
    by the real, unmodified SuperResolutionProcessor preprocessing path,
    end to end — not just structurally compatible in theory."""
    import tifffile

    from app.services.satellite.gee import _reflectance_to_uint8_rgb

    raw_reflectance = (np.random.rand(3, 16, 16) * 4000).astype(np.uint16)  # realistic S2 SR values
    rgb_uint8 = _reflectance_to_uint8_rgb(raw_reflectance)
    input_path = tmp_path / "gee_scene.tif"
    tifffile.imwrite(input_path, rgb_uint8, photometric="rgb")

    monkeypatch.setattr(get_settings(), "sr_checkpoint_path", str(trained_checkpoint))
    processor = SuperResolutionProcessor()

    image = Image(
        filename="gee_scene.tif",
        stored_filename=f"{uuid.uuid4().hex}.tif",
        file_path=str(input_path),
        file_type="image/tiff",
        file_size=input_path.stat().st_size,
        width=16,
        height=16,
    )
    session = db_module.SessionLocal()
    try:
        session.add(image)
        session.commit()
        session.refresh(image)

        job = ProcessingJob(
            image_id=image.id,
            analysis_name="GEE compatibility test",
            scale_factor=2,
            status=JobStatus.QUEUED,
            progress=0,
        )
        session.add(job)
        session.commit()
        session.refresh(job)

        processor.run(job.id)
        session.refresh(job)

        assert job.status == JobStatus.COMPLETED

        from app.services import result_service

        result = result_service.get_result_by_job(session, job.id)
        assert result is not None
        assert result.is_mock is False
        assert result.metrics_available is False  # never fabricated
        assert result.psnr is None
        assert result.ssim is None
        # 16x16 input, 2x model -> 32x32 output — actually produced, not assumed.
        assert result.output_width == 32
        assert result.output_height == 32
    finally:
        session.close()


def test_upload_workflow_never_calls_satellite_service(monkeypatch, tmp_path, trained_checkpoint):
    """Workflow A (Phase 6.2): an uploaded-image job must reach
    SuperResolutionProcessor directly through ProcessingService, never
    through SatelliteService — that layer exists only for AOI-driven jobs.
    Spies on acquire_scene_for_job to prove it is structurally never
    invoked here, not just that the job happens to succeed."""
    monkeypatch.setattr(get_settings(), "sr_checkpoint_path", str(trained_checkpoint))
    monkeypatch.setattr(get_settings(), "processor_mode", "super_resolution")
    monkeypatch.setattr(processing_service, "_processor", processing_service._build_processor())

    from app.services.satellite import service as satellite_service

    def _must_not_be_called(*args, **kwargs):
        raise AssertionError("acquire_scene_for_job must not run for an uploaded-image job")

    monkeypatch.setattr(satellite_service, "acquire_scene_for_job", _must_not_be_called)

    session = db_module.SessionLocal()
    try:
        job = _make_image_job(session, tmp_path, scale_factor=2, size=(16, 16))
        processing_service._run_job_pipeline(job.id)
        session.refresh(job)

        assert job.status == JobStatus.COMPLETED

        from app.services import result_service

        result = result_service.get_result_by_job(session, job.id)
        assert result is not None
        assert result.is_mock is False
        assert result.model_name == "edsr_satellite"
    finally:
        session.close()


def test_aoi_workflow_reaches_real_processor(monkeypatch, tmp_path, trained_checkpoint):
    """Workflow B (Phase 6.2), as far as this environment can honestly test
    it: with no real Copernicus credentials available, this uses
    FakeSatelliteProvider (same interface as CopernicusSatelliteProvider,
    see fake.py) to prove the AOI -> SatelliteService -> SuperResolutionProcessor
    chain actually reaches the real processor. It intentionally does NOT
    assert job completion — the fake provider's stub download bytes aren't a
    real decodable image, so the honest outcome is a clean AI-inference
    failure, which is itself the proof this reached the real processor
    (a mock fallback would have "succeeded" instead). Real Copernicus
    acquisition itself is NOT exercised by this test — see backend/README.md
    Phase 6.2 section for why that couldn't be tested live in this session.
    """
    monkeypatch.setattr(get_settings(), "sr_checkpoint_path", str(trained_checkpoint))
    monkeypatch.setattr(get_settings(), "processor_mode", "super_resolution")
    monkeypatch.setattr(processing_service, "_processor", processing_service._build_processor())

    from app.services.satellite import service as satellite_service
    from app.services.satellite.fake import FakeSatelliteProvider

    monkeypatch.setattr(satellite_service, "_provider", FakeSatelliteProvider())

    session = db_module.SessionLocal()
    try:
        job = ProcessingJob(
            image_id=None,
            analysis_name="AOI real-processor chain test",
            scale_factor=2,
            aoi_geometry={"north": 25.7, "south": 20.6, "east": 81.6, "west": 72.4},
            status=JobStatus.QUEUED,
            progress=0,
        )
        session.add(job)
        session.commit()
        session.refresh(job)

        processing_service._run_job_pipeline(job.id)
        session.refresh(job)

        # A real scene row was created by the (fake) satellite acquisition...
        assert job.satellite_scene is not None
        assert job.satellite_scene.download_status == "completed"
        # ...and it really was handed to SuperResolutionProcessor: the job
        # failed at AI inference (undecodable stub bytes), not at satellite
        # acquisition (current_stage would still read 'satellite_acquisition'
        # for that) and not silently via MockProcessor (no psnr/ssim result).
        assert job.status == JobStatus.FAILED
        assert job.current_stage != processing_service.SATELLITE_STAGE
        assert "ai inference failed" in job.error_message.lower()
    finally:
        session.close()
