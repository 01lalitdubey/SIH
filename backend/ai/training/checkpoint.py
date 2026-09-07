"""Checkpoint save/load with the metadata Phase 6 §18 requires: model name,
scale factor, input channels, training dataset, epoch, validation loss,
and training configuration — enough to reconstruct the exact architecture
(EDSRLite.from_config) and know exactly what produced it, without needing
a second sidecar file.
"""

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import torch

from ai.models.edsr import EDSRLite


@dataclass
class CheckpointMetadata:
    model_name: str
    dataset: str
    epoch: int
    val_loss: float
    val_psnr: float | None
    val_ssim: float | None
    training_config: dict[str, Any] = field(default_factory=dict)


def save_checkpoint(path: Path, model: EDSRLite, metadata: CheckpointMetadata) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    torch.save(
        {
            "model_state_dict": model.state_dict(),
            "model_config": model.config(),
            "metadata": asdict(metadata),
        },
        path,
    )


class CheckpointError(Exception):
    """Raised for a missing, unreadable, or structurally invalid checkpoint
    file — surfaced by SuperResolutionProcessor as a clear configuration
    error, never silently swallowed into a mock fallback."""


def load_checkpoint(path: Path, device: torch.device) -> tuple[EDSRLite, dict]:
    if not path.is_file():
        raise CheckpointError(f"Checkpoint not found at '{path}'.")

    try:
        checkpoint = torch.load(path, map_location=device, weights_only=True)
    except Exception as exc:  # noqa: BLE001 - genuinely any torch.load failure is a config error here
        raise CheckpointError(f"Checkpoint at '{path}' could not be read: {exc}") from exc

    for key in ("model_state_dict", "model_config"):
        if key not in checkpoint:
            raise CheckpointError(f"Checkpoint at '{path}' is missing required key '{key}'.")

    model = EDSRLite.from_config(checkpoint["model_config"])
    model.load_state_dict(checkpoint["model_state_dict"])
    model.to(device)
    model.eval()
    return model, checkpoint.get("metadata", {})
