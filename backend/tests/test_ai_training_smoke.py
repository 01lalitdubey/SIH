"""TRAINING SMOKE TEST — proves Dataset -> DataLoader -> model -> loss ->
backprop -> optimizer -> checkpoint actually works, using tiny synthetic
tensors (TinySyntheticSRDataset). This is NOT a satellite training
experiment and must never be reported as one — see
ai/training/train.py's module docstring and docs/ARCHITECTURE.md §19 for
where the real SEN2VENuS experiment (network-dependent, run separately) is
documented instead.

No network access, no GPU requirement, deterministic, runs in well under a
second — safe to run in every CI/normal test invocation.
"""

import pytest

torch = pytest.importorskip("torch")

from torch.utils.data import DataLoader  # noqa: E402

from ai.datasets.sen2venus import TinySyntheticSRDataset  # noqa: E402
from ai.losses.reconstruction import CharbonnierLoss, get_loss  # noqa: E402
from ai.metrics.image_metrics import psnr, ssim  # noqa: E402
from ai.models.edsr import EDSRLite  # noqa: E402
from ai.training.checkpoint import (  # noqa: E402
    CheckpointError,
    CheckpointMetadata,
    load_checkpoint,
    save_checkpoint,
)
from ai.training.train import TrainingConfig, run_training  # noqa: E402


def test_synthetic_dataset_shapes():
    ds = TinySyntheticSRDataset(num_samples=4, channels=3, hr_size=16, scale_factor=2)
    lr, hr = ds[0]
    assert lr.shape == (3, 8, 8)
    assert hr.shape == (3, 16, 16)
    assert len(ds) == 4


def test_dataloader_batches_synthetic_dataset():
    ds = TinySyntheticSRDataset(num_samples=6, channels=3, hr_size=16, scale_factor=2)
    loader = DataLoader(ds, batch_size=2)
    batches = list(loader)
    assert len(batches) == 3
    lr_batch, hr_batch = batches[0]
    assert lr_batch.shape == (2, 3, 8, 8)


def test_backpropagation_actually_reduces_loss():
    """The real proof this is trainable: loss on a fixed tiny batch goes
    down after a few optimizer steps, not just "the code runs"."""
    torch.manual_seed(0)
    model = EDSRLite(in_channels=3, num_features=16, num_res_blocks=2, scale_factor=2)
    optimizer = torch.optim.Adam(model.parameters(), lr=1e-2)
    loss_fn = get_loss("l1")

    lr_input = torch.rand(4, 3, 8, 8)
    hr_target = torch.rand(4, 3, 16, 16)

    losses = []
    for _ in range(20):
        optimizer.zero_grad()
        loss = loss_fn(model(lr_input), hr_target)
        loss.backward()
        optimizer.step()
        losses.append(loss.item())

    assert losses[-1] < losses[0]


def test_charbonnier_loss_is_finite_and_nonnegative():
    loss_fn = CharbonnierLoss()
    pred = torch.rand(2, 3, 8, 8)
    target = torch.rand(2, 3, 8, 8)
    value = loss_fn(pred, target)
    assert torch.isfinite(value)
    assert value.item() >= 0


def test_get_loss_rejects_unknown_name():
    with pytest.raises(ValueError):
        get_loss("not_a_real_loss")


def test_psnr_and_ssim_are_real_computations_not_fabricated():
    """Identical images -> perfect scores; this is the actual math running,
    not a placeholder returning a plausible constant."""
    image = torch.rand(1, 3, 32, 32)
    assert psnr(image, image) == float("inf")
    assert ssim(image, image) == pytest.approx(1.0, abs=1e-4)

    noisy = image + 0.5
    noisy_psnr = psnr(image, noisy.clamp(0, 1))
    assert 0 < noisy_psnr < 100  # a real, finite, sane dB value — not inf, not fabricated


def test_full_training_smoke_run_and_checkpoint_reload(tmp_path, monkeypatch):
    """The end-to-end proof required by §29: dataset -> loader -> model ->
    loss -> backprop -> optimizer -> checkpoint, then reload and infer."""
    import ai.training.train as train_module

    monkeypatch.setattr(train_module, "CHECKPOINT_DIR", tmp_path)

    config = TrainingConfig(
        dataset="synthetic",
        epochs=2,
        batch_size=4,
        num_features=8,
        num_res_blocks=1,
        max_train_samples=8,
        max_val_samples=4,
        checkpoint_name="smoke_test.pt",
    )
    result = run_training(config)

    assert len(result["history"]) == 2
    checkpoint_path = tmp_path / "smoke_test.pt"
    assert checkpoint_path.is_file()

    model, metadata = load_checkpoint(checkpoint_path, torch.device("cpu"))
    assert metadata["dataset"] == "synthetic"
    assert metadata["epoch"] in (1, 2)

    # Reloaded model actually runs inference.
    output = model(torch.rand(1, 3, 8, 8))
    assert output.shape == (1, 3, 16, 16)


def test_checkpoint_missing_file_raises_clear_error(tmp_path):
    with pytest.raises(CheckpointError, match="not found"):
        load_checkpoint(tmp_path / "does_not_exist.pt", torch.device("cpu"))


def test_checkpoint_malformed_file_raises_clear_error(tmp_path):
    bad_path = tmp_path / "bad.pt"
    torch.save({"unexpected": "structure"}, bad_path)
    with pytest.raises(CheckpointError, match="missing required key"):
        load_checkpoint(bad_path, torch.device("cpu"))


def test_checkpoint_round_trip_preserves_metadata(tmp_path):
    model = EDSRLite(in_channels=3, num_features=8, num_res_blocks=1, scale_factor=2)
    path = tmp_path / "meta_test.pt"
    save_checkpoint(
        path,
        model,
        CheckpointMetadata(
            model_name="edsr_satellite",
            dataset="synthetic",
            epoch=5,
            val_loss=0.1234,
            val_psnr=25.5,
            val_ssim=0.8,
            training_config={"batch_size": 4},
        ),
    )
    _, metadata = load_checkpoint(path, torch.device("cpu"))
    assert metadata["epoch"] == 5
    assert metadata["val_psnr"] == 25.5
    assert metadata["training_config"]["batch_size"] == 4
