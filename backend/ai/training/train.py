"""Training entry point. Not a FastAPI route — training logic lives here,
called from the command line:

    python -m ai.training.train --dataset synthetic --epochs 2   (smoke test)
    python -m ai.training.train --dataset sen2venus --epochs 5 --max-train-samples 64 --max-val-samples 16

The `synthetic` dataset is the TRAINING SMOKE TEST path (tiny, deterministic,
network-free — proves the pipeline mechanics work). The `sen2venus` dataset
is real Sentinel-2/VENuS data fetched over the network per
ai/datasets/sen2venus.py — see docs/ARCHITECTURE.md §18/§19 for exactly
what was run and what it does (and doesn't) demonstrate scientifically.
"""

import argparse
import random
import time
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import torch
from torch.utils.data import DataLoader

from ai.losses.reconstruction import get_loss
from ai.metrics.image_metrics import psnr, ssim
from ai.models.edsr import EDSRLite
from ai.training.checkpoint import CheckpointMetadata, save_checkpoint

CHECKPOINT_DIR = Path(__file__).resolve().parent.parent / "checkpoints"


@dataclass
class TrainingConfig:
    dataset: str = "synthetic"  # "synthetic" | "sen2venus"
    epochs: int = 2
    batch_size: int = 8
    learning_rate: float = 1e-4
    seed: int = 42
    num_channels: int = 3
    num_features: int = 64
    num_res_blocks: int = 8
    scale_factor: int = 2
    loss_name: str = "l1"
    max_train_samples: int | None = 64
    max_val_samples: int | None = 16
    checkpoint_name: str = "edsr_satellite.pt"
    device: str | None = None  # None = auto-detect


def set_seed(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


def resolve_device(requested: str | None) -> torch.device:
    if requested:
        return torch.device(requested)
    return torch.device("cuda" if torch.cuda.is_available() else "cpu")


def build_datasets(config: TrainingConfig):
    if config.dataset == "synthetic":
        from ai.datasets.sen2venus import TinySyntheticSRDataset

        train_ds = TinySyntheticSRDataset(
            num_samples=config.max_train_samples or 32,
            channels=config.num_channels,
            hr_size=32,
            scale_factor=config.scale_factor,
            seed=config.seed,
        )
        val_ds = TinySyntheticSRDataset(
            num_samples=config.max_val_samples or 8,
            channels=config.num_channels,
            hr_size=32,
            scale_factor=config.scale_factor,
            seed=config.seed + 1,
        )
        return train_ds, val_ds

    if config.dataset == "sen2venus":
        from ai.datasets.sen2venus import Sen2VenusDataset

        train_ds = Sen2VenusDataset("train", max_samples=config.max_train_samples, seed=config.seed)
        val_ds = Sen2VenusDataset("val", max_samples=config.max_val_samples, seed=config.seed)
        return train_ds, val_ds

    raise ValueError(f"Unknown dataset '{config.dataset}'. Expected 'synthetic' or 'sen2venus'.")


def train_one_epoch(model, loader, loss_fn, optimizer, device) -> float:
    model.train()
    total_loss = 0.0
    for lr_batch, hr_batch in loader:
        lr_batch, hr_batch = lr_batch.to(device), hr_batch.to(device)
        optimizer.zero_grad()
        pred = model(lr_batch)
        loss = loss_fn(pred, hr_batch)
        loss.backward()
        optimizer.step()
        total_loss += loss.item() * lr_batch.size(0)
    return total_loss / len(loader.dataset)


@torch.no_grad()
def validate(model, loader, loss_fn, device) -> dict:
    model.eval()
    total_loss = 0.0
    psnr_values: list[float] = []
    ssim_values: list[float] = []
    for lr_batch, hr_batch in loader:
        lr_batch, hr_batch = lr_batch.to(device), hr_batch.to(device)
        pred = model(lr_batch)
        loss = loss_fn(pred, hr_batch)
        total_loss += loss.item() * lr_batch.size(0)
        clamped = pred.clamp(0.0, 1.0)
        for i in range(pred.size(0)):
            psnr_values.append(psnr(clamped[i], hr_batch[i]))
            ssim_values.append(ssim(clamped[i], hr_batch[i]))

    return {
        "loss": total_loss / len(loader.dataset),
        "psnr": float(np.mean(psnr_values)) if psnr_values else None,
        "ssim": float(np.mean(ssim_values)) if ssim_values else None,
    }


def run_training(config: TrainingConfig) -> dict:
    set_seed(config.seed)
    device = resolve_device(config.device)

    train_ds, val_ds = build_datasets(config)
    train_loader = DataLoader(train_ds, batch_size=config.batch_size, shuffle=True)
    val_loader = DataLoader(val_ds, batch_size=config.batch_size, shuffle=False)

    model = EDSRLite(
        in_channels=config.num_channels,
        num_features=config.num_features,
        num_res_blocks=config.num_res_blocks,
        scale_factor=config.scale_factor,
    ).to(device)
    loss_fn = get_loss(config.loss_name)
    optimizer = torch.optim.AdamW(model.parameters(), lr=config.learning_rate)

    print(f"[train] device={device} params={model.count_parameters():,} "
          f"train_samples={len(train_ds)} val_samples={len(val_ds)}")

    history = []
    best_val_loss = float("inf")
    checkpoint_path = CHECKPOINT_DIR / config.checkpoint_name

    for epoch in range(1, config.epochs + 1):
        start = time.monotonic()
        train_loss = train_one_epoch(model, train_loader, loss_fn, optimizer, device)
        val_metrics = validate(model, val_loader, loss_fn, device)
        elapsed = time.monotonic() - start

        print(
            f"[train] epoch {epoch}/{config.epochs} "
            f"train_loss={train_loss:.5f} val_loss={val_metrics['loss']:.5f} "
            f"val_psnr={val_metrics['psnr']} val_ssim={val_metrics['ssim']} "
            f"({elapsed:.1f}s)"
        )
        history.append({"epoch": epoch, "train_loss": train_loss, **val_metrics})

        if val_metrics["loss"] < best_val_loss:
            best_val_loss = val_metrics["loss"]
            save_checkpoint(
                checkpoint_path,
                model,
                CheckpointMetadata(
                    model_name="edsr_satellite",
                    dataset=config.dataset,
                    epoch=epoch,
                    val_loss=val_metrics["loss"],
                    val_psnr=val_metrics["psnr"],
                    val_ssim=val_metrics["ssim"],
                    training_config=vars(config),
                ),
            )
            print(f"[train] saved checkpoint -> {checkpoint_path}")

    if hasattr(train_ds, "close"):
        train_ds.close()
    if hasattr(val_ds, "close"):
        val_ds.close()

    return {"history": history, "checkpoint_path": str(checkpoint_path), "best_val_loss": best_val_loss}


def _parse_args() -> TrainingConfig:
    parser = argparse.ArgumentParser(description="Train the satellite EDSR-lite SR model.")
    parser.add_argument("--dataset", choices=["synthetic", "sen2venus"], default="synthetic")
    parser.add_argument("--epochs", type=int, default=2)
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--learning-rate", type=float, default=1e-4)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--num-features", type=int, default=64)
    parser.add_argument("--num-res-blocks", type=int, default=8)
    parser.add_argument("--scale-factor", type=int, default=2, choices=[2, 4])
    parser.add_argument("--loss", dest="loss_name", default="l1", choices=["l1", "charbonnier"])
    parser.add_argument("--max-train-samples", type=int, default=64)
    parser.add_argument("--max-val-samples", type=int, default=16)
    parser.add_argument("--checkpoint-name", default="edsr_satellite.pt")
    parser.add_argument("--device", default=None)
    args = parser.parse_args()
    return TrainingConfig(
        dataset=args.dataset,
        epochs=args.epochs,
        batch_size=args.batch_size,
        learning_rate=args.learning_rate,
        seed=args.seed,
        num_features=args.num_features,
        num_res_blocks=args.num_res_blocks,
        scale_factor=args.scale_factor,
        loss_name=args.loss_name,
        max_train_samples=args.max_train_samples,
        max_val_samples=args.max_val_samples,
        checkpoint_name=args.checkpoint_name,
        device=args.device,
    )


if __name__ == "__main__":
    run_training(_parse_args())
