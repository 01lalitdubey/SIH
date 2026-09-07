"""Visual validation (Phase 6 brief §31) — not a test, a manual inspection
tool. Loads a trained checkpoint, runs it on a handful of real held-out
SEN2VENuS validation patches, and writes LR / SR / HR side-by-side PNGs so
artifacts (blur, checkerboarding, color shift, hallucinated structure) can
actually be looked at rather than inferred from a PSNR number alone.

    python -m ai.inference.visual_check --checkpoint ai/checkpoints/edsr_satellite.pt --num-samples 4
"""

import argparse
from pathlib import Path

import numpy as np
import torch
from PIL import Image as PILImage

from ai.inference.infer import load_engine

OUTPUT_DIR = Path(__file__).resolve().parent.parent / "checkpoints" / "visual_checks"


def _to_uint8(array: np.ndarray) -> np.ndarray:
    return (np.clip(array, 0.0, 1.0).transpose(1, 2, 0) * 255.0).round().astype(np.uint8)


def _upscale_nearest_for_display(array_uint8: np.ndarray, target_hw: tuple[int, int]) -> np.ndarray:
    img = PILImage.fromarray(array_uint8)
    return np.array(img.resize((target_hw[1], target_hw[0]), PILImage.Resampling.NEAREST))


def run(checkpoint_path: Path, num_samples: int, seed: int) -> None:
    from ai.datasets.sen2venus import Sen2VenusDataset

    engine = load_engine(checkpoint_path)
    dataset = Sen2VenusDataset("val", max_samples=num_samples, seed=seed)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    for i in range(len(dataset)):
        lr_tensor, hr_tensor = dataset[i]
        lr_array = lr_tensor.numpy()
        hr_array = hr_tensor.numpy()

        with torch.no_grad():
            result = engine.infer_array(lr_array)
        sr_array = result.output

        lr_uint8 = _to_uint8(lr_array)
        sr_uint8 = _to_uint8(sr_array)
        hr_uint8 = _to_uint8(hr_array)

        lr_display = _upscale_nearest_for_display(lr_uint8, hr_uint8.shape[:2])
        panel = np.concatenate([lr_display, sr_uint8, hr_uint8], axis=1)

        out_path = OUTPUT_DIR / f"sample_{i:02d}_LR-nearest_SR_HR.png"
        PILImage.fromarray(panel).save(out_path)
        print(f"[visual_check] wrote {out_path}")

    dataset.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Visual LR/SR/HR comparison panels.")
    parser.add_argument("--checkpoint", default="ai/checkpoints/edsr_satellite.pt")
    parser.add_argument("--num-samples", type=int, default=4)
    parser.add_argument("--seed", type=int, default=123)
    args = parser.parse_args()
    run(Path(args.checkpoint), args.num_samples, args.seed)
