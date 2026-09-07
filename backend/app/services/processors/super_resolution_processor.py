"""Real PyTorch super-resolution processor — the Phase 6 counterpart to
MockProcessor, behind the same BaseProcessor interface.

    ProcessingService
          |
          v
    Processor Interface (BaseProcessor)
          |
          v
    MockProcessor              <- Phase 3, unchanged, still available
    SuperResolutionProcessor   <- Phase 6 (this file)
          |
          v
    ai/inference/infer.py -> ai/models/edsr.py (trained checkpoint)

Selected via PROCESSOR_MODE=super_resolution (app/core/config.py). Per the
Phase 6 brief: a missing/broken checkpoint must fail the job with a clear
configuration error, never fall back to MockProcessor silently — that
fallback would make a real-looking result that was actually mock, which is
exactly the kind of fabrication this phase forbids.

Real vs. still-mocked in this processor's own output:
  - REAL: model architecture, trained weights, tensor inference, device,
    inference time.
  - NOT computed here: psnr/ssim/lpips. Production inference has no
    ground-truth HR image to compare against (that's the entire point of
    running SR) — metrics_available is always False and the metric fields
    stay null, per §24 of the Phase 6 brief. Real PSNR/SSIM DO get
    computed, but only during training/validation against the held-out
    region split — see ai/training/train.py's validate().
"""

import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from PIL import Image as PILImage

from app.core import database as db
from app.core.config import get_settings
from app.models.processing_job import JobStatus, ProcessingJob, ProcessingStage
from app.models.result import Result
from app.services.processors.base import BaseProcessor

settings = get_settings()


class SuperResolutionProcessor(BaseProcessor):
    def __init__(self) -> None:
        self._engine = None
        self._init_error: str | None = None
        self._load_engine()

    def _load_engine(self) -> None:
        from ai.inference.infer import load_engine
        from ai.training.checkpoint import CheckpointError

        try:
            self._engine = load_engine(settings.sr_checkpoint_full_path, settings.sr_device)
        except CheckpointError as exc:
            # Deferred, not fatal at import time — the app must still start
            # on a machine with no checkpoint configured (§20). The first
            # job that actually needs this processor will fail clearly.
            self._init_error = str(exc)

    def run(self, job_id: uuid.UUID) -> None:
        session = db.SessionLocal()
        try:
            job = session.get(ProcessingJob, job_id)
            if job is None:
                return

            job.status = JobStatus.PROCESSING
            job.started_at = job.started_at or datetime.now(timezone.utc)
            session.commit()

            if self._engine is None:
                self._fail(session, job, f"Super-resolution model is not available: {self._init_error}")
                return

            if job.scale_factor != self._engine.scale_factor:
                self._fail(
                    session,
                    job,
                    f"The trained model only supports {self._engine.scale_factor}x, "
                    f"but this job requested {job.scale_factor}x.",
                )
                return

            input_path = self._resolve_input_path(job)
            if input_path is None:
                self._fail(
                    session,
                    job,
                    "No input imagery available for super-resolution "
                    "(no uploaded image and no downloaded satellite scene file).",
                )
                return

            # Phase 6.2: an AOI job's input is whatever the satellite layer
            # downloaded (a real Sentinel-2 quicklook once Copernicus
            # credentials are configured) — a format this model can't decode,
            # or any other unexpected failure in this block, must fail the
            # job cleanly rather than leave it stuck in "processing" forever
            # (an uncaught exception here would otherwise crash silently in
            # the background task with no job-status update at all).
            try:
                job.current_stage = ProcessingStage.PREPROCESSING
                job.progress = 20
                session.commit()
                lr_array = self._load_and_normalize(input_path)

                job.current_stage = ProcessingStage.FEATURE_EXTRACTION
                job.progress = 40
                session.commit()

                job.current_stage = ProcessingStage.SUPER_RESOLUTION
                job.progress = 60
                session.commit()
                inference_result = self._engine.infer_array(lr_array)

                job.current_stage = ProcessingStage.POST_PROCESSING
                job.progress = 80
                session.commit()
                output_path, out_width, out_height = self._save_output(job, inference_result.output)
            except Exception as exc:  # noqa: BLE001 - any failure here is a real, reportable inference failure
                self._fail(session, job, f"AI inference failed while processing the input imagery: {exc}")
                return

            job.current_stage = ProcessingStage.EVALUATION
            job.progress = 95
            session.commit()

            result = Result(
                job_id=job.id,
                output_path=output_path,
                # No ground-truth HR image exists for a real inference job
                # — never invented. See ai/training/train.py for where real
                # PSNR/SSIM actually get computed (against held-out data).
                psnr=None,
                ssim=None,
                lpips=None,
                metrics_available=False,
                processing_time=inference_result.inference_time_seconds,
                output_width=out_width,
                output_height=out_height,
                is_mock=False,
                model_name=inference_result.model_name,
                model_version=f"scale{inference_result.scale_factor}x",
                device=inference_result.device,
            )
            session.add(result)

            job.status = JobStatus.COMPLETED
            job.progress = 100
            job.completed_at = datetime.now(timezone.utc)
            session.commit()
        finally:
            session.close()

    def _fail(self, session, job: ProcessingJob, message: str) -> None:
        job.status = JobStatus.FAILED
        job.error_message = message
        job.completed_at = datetime.now(timezone.utc)
        session.commit()

    def _resolve_input_path(self, job: ProcessingJob) -> Path | None:
        if job.image is not None:
            return Path(job.image.file_path)
        scene = job.satellite_scene
        if scene is not None and scene.download_path:
            return Path(scene.download_path)
        return None

    def _load_and_normalize(self, path: Path) -> np.ndarray:
        """Real Sentinel-2 scenes downloaded in Phase 5 are quicklook JPEGs
        (see backend/app/services/satellite/copernicus.py) or a capped
        full product; ordinary uploads are 8-bit JPEG/PNG. Neither is the
        16-bit reflectance*10000 data the model trained on — see
        docs/ARCHITECTURE.md §19 "Domain gap" for why this is a real,
        documented limitation rather than a hidden assumption. uint16
        TIFF input (closer to raw Sentinel-2 reflectance) is normalized
        the same way as training data; anything else is treated as an
        8-bit visual image."""
        with PILImage.open(path) as img:
            img = img.convert("RGB")
            array = np.array(img)

        channels_first = array.transpose(2, 0, 1).astype(np.float32)
        if array.dtype == np.uint16:
            normalized = channels_first / 10000.0
        else:
            normalized = channels_first / 255.0
        return np.clip(normalized, 0.0, 1.0)

    def _save_output(self, job: ProcessingJob, output_array: np.ndarray) -> tuple[str, int, int]:
        image_uint8 = (output_array.transpose(1, 2, 0) * 255.0).round().astype(np.uint8)
        output_image = PILImage.fromarray(image_uint8, mode="RGB")

        output_filename = f"{job.id.hex}_sr_output.png"
        output_path = settings.output_path / output_filename
        output_image.save(output_path)
        return str(output_path), output_image.width, output_image.height
