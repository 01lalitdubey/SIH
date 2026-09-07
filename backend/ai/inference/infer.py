"""Inference-only path — loads a trained checkpoint once and reuses it for
every call. Never trains. This is what SuperResolutionProcessor calls; the
FastAPI process never touches ai/training/*.

Tiling (§16 of the Phase 6 brief): the model is fully convolutional, so it
can technically run on an image of any size in one shot, but a full
satellite scene could be large enough to be impractical to hold as one
tensor. `infer_array` tiles with a small context margin per tile (fetch
extra border pixels from neighbors, crop back to the tile's own region
after upscaling) so tile seams don't show up as a hard grid in the output,
without the extra complexity of seam-blending.
"""

import time
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import torch

from ai.training.checkpoint import CheckpointError, load_checkpoint

TILE_SIZE = 128
TILE_MARGIN = 8


@dataclass
class InferenceResult:
    output: np.ndarray  # (C, H*scale, W*scale), float32 in [0, 1]
    device: str
    model_name: str
    scale_factor: int
    inference_time_seconds: float


class SRInferenceEngine:
    """Loads once, reused across requests — see SuperResolutionProcessor,
    which keeps one instance for the process lifetime rather than
    reloading the checkpoint per job."""

    def __init__(self, checkpoint_path: Path, device: str | None = None) -> None:
        self.device = torch.device(device) if device else torch.device(
            "cuda" if torch.cuda.is_available() else "cpu"
        )
        # Raises CheckpointError on anything wrong — the caller (processor)
        # must not catch this and silently fall back to a mock.
        self.model, self.checkpoint_metadata = load_checkpoint(checkpoint_path, self.device)
        self.scale_factor = self.model.scale_factor
        self.in_channels = self.model.in_channels

    def infer_array(self, lr_array: np.ndarray) -> InferenceResult:
        """lr_array: (C, H, W) float32 in [0, 1], C == self.in_channels."""
        if lr_array.shape[0] != self.in_channels:
            raise ValueError(
                f"Model expects {self.in_channels} channels, got array with shape {lr_array.shape}."
            )

        start = time.monotonic()
        _, height, width = lr_array.shape

        if height <= TILE_SIZE and width <= TILE_SIZE:
            output = self._infer_tensor(lr_array)
        else:
            output = self._infer_tiled(lr_array)

        elapsed = time.monotonic() - start
        return InferenceResult(
            output=output,
            device=str(self.device),
            model_name=self.checkpoint_metadata.get("model_name", "edsr_satellite"),
            scale_factor=self.scale_factor,
            inference_time_seconds=elapsed,
        )

    @torch.no_grad()
    def _infer_tensor(self, array: np.ndarray) -> np.ndarray:
        tensor = torch.from_numpy(array).unsqueeze(0).to(self.device)
        output = self.model(tensor)
        return output.squeeze(0).clamp(0.0, 1.0).cpu().numpy()

    def _infer_tiled(self, array: np.ndarray) -> np.ndarray:
        channels, height, width = array.shape
        scale = self.scale_factor
        output = np.zeros((channels, height * scale, width * scale), dtype=np.float32)

        for y0 in range(0, height, TILE_SIZE):
            for x0 in range(0, width, TILE_SIZE):
                y1, x1 = min(y0 + TILE_SIZE, height), min(x0 + TILE_SIZE, width)

                # Padded region: tile plus a context margin, clamped to image bounds.
                py0, py1 = max(0, y0 - TILE_MARGIN), min(height, y1 + TILE_MARGIN)
                px0, px1 = max(0, x0 - TILE_MARGIN), min(width, x1 + TILE_MARGIN)
                padded_tile = array[:, py0:py1, px0:px1]

                sr_padded = self._infer_tensor(padded_tile)

                # Crop the padded output back down to just this tile's own
                # (upscaled) region, discarding the borrowed context margin.
                crop_top = (y0 - py0) * scale
                crop_left = (x0 - px0) * scale
                tile_h = (y1 - y0) * scale
                tile_w = (x1 - x0) * scale
                sr_tile = sr_padded[:, crop_top : crop_top + tile_h, crop_left : crop_left + tile_w]

                output[:, y0 * scale : y1 * scale, x0 * scale : x1 * scale] = sr_tile

        return output


def load_engine(checkpoint_path: Path, device: str | None = None) -> SRInferenceEngine:
    """Thin wrapper so callers get CheckpointError, not an arbitrary
    exception, if the checkpoint is missing or malformed."""
    try:
        return SRInferenceEngine(checkpoint_path, device)
    except CheckpointError:
        raise
    except Exception as exc:  # noqa: BLE001 - any other load-time failure is still a config error
        raise CheckpointError(f"Failed to initialize the SR model from '{checkpoint_path}': {exc}") from exc
