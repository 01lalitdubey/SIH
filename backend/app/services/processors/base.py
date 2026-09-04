import uuid
from abc import ABC, abstractmethod


class BaseProcessor(ABC):
    """Interface every super-resolution processor must implement.

    ProcessingService
          |
          v
    Processor Interface (this class)
          |
          v
    MockProcessor              <- CURRENT (this phase)
    RealSatelliteProcessor     <- FUTURE (Phase 6+)
          |
          v
    SuperResolutionModel       <- FUTURE (Phase 6+)

    `run` owns the full lifecycle of one job: advancing its status/progress/
    current_stage through to completion (or a controlled failure) and
    persisting a Result row on success. It takes only a job id, not a live
    session, because implementations typically execute in a background
    thread and must manage their own database session rather than share
    one across threads.
    """

    @abstractmethod
    def run(self, job_id: uuid.UUID) -> None:
        raise NotImplementedError
