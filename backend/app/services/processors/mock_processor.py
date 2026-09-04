import random
import time
import uuid
from datetime import datetime, timezone

from PIL import Image as PILImage

from app.core import database as db
from app.core.config import get_settings
from app.models.processing_job import JobStatus, ProcessingJob, ProcessingStage
from app.models.result import Result
from app.services.processors.base import BaseProcessor

settings = get_settings()

STAGE_DURATION_SECONDS = 1.0

# The stage a "simulate failure" run stops at — mirrors the frontend's own
# demo failure (Process.jsx: MOCK_FAILURE_STAGE = 2 = "Super Resolution").
FAILURE_STAGE = ProcessingStage.SUPER_RESOLUTION


class MockProcessor(BaseProcessor):
    """MOCK/TEMPORARY — simulates the 5-stage pipeline with real DB writes
    and (when an input image exists) a real Pillow resize, but no actual
    super-resolution model. Swapped for a real processor behind the same
    BaseProcessor interface once Phase 6 lands.
    """

    def run(self, job_id: uuid.UUID) -> None:
        session = db.SessionLocal()
        try:
            job = session.get(ProcessingJob, job_id)
            if job is None:
                return

            job.status = JobStatus.PROCESSING
            job.started_at = datetime.now(timezone.utc)
            session.commit()

            start_time = time.monotonic()

            for index, stage in enumerate(ProcessingStage.ORDERED):
                time.sleep(STAGE_DURATION_SECONDS)

                if job.simulate_failure and stage == FAILURE_STAGE:
                    job.status = JobStatus.FAILED
                    job.current_stage = stage
                    job.error_message = (
                        f"Mock failure triggered during '{stage}' for demo purposes."
                    )
                    session.commit()
                    return

                job.current_stage = stage
                job.progress = round(((index + 1) / len(ProcessingStage.ORDERED)) * 100)
                session.commit()

            elapsed = time.monotonic() - start_time

            output_path, out_width, out_height = self._generate_mock_output(job)

            result = Result(
                job_id=job.id,
                output_path=output_path,
                psnr=round(random.uniform(28.0, 34.0), 2),
                ssim=round(random.uniform(0.85, 0.96), 3),
                lpips=round(random.uniform(0.05, 0.15), 3),
                processing_time=round(elapsed, 2),
                output_width=out_width,
                output_height=out_height,
            )
            session.add(result)

            job.status = JobStatus.COMPLETED
            job.completed_at = datetime.now(timezone.utc)
            session.commit()
        finally:
            session.close()

    def _generate_mock_output(
        self, job: ProcessingJob
    ) -> tuple[str | None, int | None, int | None]:
        """Best-effort: if the job has an input image, produce a real
        upscaled file via a plain Pillow resize (classic image processing,
        not AI) so output_path/width/height reflect something real. AOI-only
        jobs (no uploaded image) have no file to resize yet — that requires
        Phase 5's satellite fetch — so this simply returns no output file.
        """
        if job.image is None:
            return None, None, None

        try:
            with PILImage.open(job.image.file_path) as img:
                new_size = (img.width * job.scale_factor, img.height * job.scale_factor)
                upscaled = img.resize(new_size, PILImage.Resampling.BICUBIC)

                output_filename = f"{job.id.hex}_mock_output.png"
                output_path = settings.output_path / output_filename
                upscaled.save(output_path)
                return str(output_path), upscaled.width, upscaled.height
        except Exception:
            return None, None, None
