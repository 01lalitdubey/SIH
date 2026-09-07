"""Real PSNR/SSIM — computed, never randomized or fabricated.

Per the Phase 6 brief: metrics must only ever be reported when they were
actually calculated against a real ground-truth image. Both functions here
require `pred` and `target` to be real tensors; there is no code path that
returns a plausible-looking made-up number. When no ground truth exists
(e.g. real-world inference where there's no HR reference to compare
against), the caller must not invoke these at all — see
ai/inference/infer.py, which sets `metrics_available=False` in that case
rather than calling into this module.

LPIPS is intentionally not implemented here — it requires a pretrained
perceptual network (typically VGG or AlexNet weights), which is a
meaningfully heavier dependency than this MVP's scope justifies. PSNR/SSIM
are the metrics explicitly required by the Phase 6 brief; LPIPS is called
out there as optional "only if justified," and pulling in a pretrained
ImageNet-style feature extractor for one extra number isn't justified yet.
"""

import torch
import torch.nn.functional as F


def psnr(pred: torch.Tensor, target: torch.Tensor, data_range: float = 1.0) -> float:
    """Peak Signal-to-Noise Ratio, in dB. Both tensors expected in the same
    range (this codebase normalizes to [0, 1] — see datasets/sen2venus.py)."""
    mse = torch.mean((pred - target) ** 2).item()
    if mse == 0:
        return float("inf")
    return 10.0 * torch.log10(torch.tensor(data_range**2 / mse)).item()


def _gaussian_window(window_size: int, sigma: float, channels: int, device, dtype) -> torch.Tensor:
    coords = torch.arange(window_size, dtype=dtype, device=device) - window_size // 2
    g = torch.exp(-(coords**2) / (2 * sigma**2))
    g = (g / g.sum()).unsqueeze(0)
    window_2d = g.T @ g  # (window_size, window_size)
    return window_2d.expand(channels, 1, window_size, window_size).contiguous()


def ssim(
    pred: torch.Tensor,
    target: torch.Tensor,
    data_range: float = 1.0,
    window_size: int = 11,
    sigma: float = 1.5,
) -> float:
    """Single-scale SSIM (Wang et al. 2004), computed with a Gaussian
    window via depthwise convolution. Expects (N, C, H, W) tensors.

    A from-scratch implementation rather than a new dependency
    (scikit-image/pytorch-msssim) — this is the well-known reference
    formula, not an approximation, and keeps this MVP's dependency
    footprint to what training/inference actually need.
    """
    if pred.dim() == 3:
        pred = pred.unsqueeze(0)
        target = target.unsqueeze(0)

    channels = pred.shape[1]
    window = _gaussian_window(window_size, sigma, channels, pred.device, pred.dtype)
    pad = window_size // 2

    mu_pred = F.conv2d(pred, window, padding=pad, groups=channels)
    mu_target = F.conv2d(target, window, padding=pad, groups=channels)

    mu_pred_sq = mu_pred**2
    mu_target_sq = mu_target**2
    mu_pred_target = mu_pred * mu_target

    sigma_pred_sq = F.conv2d(pred * pred, window, padding=pad, groups=channels) - mu_pred_sq
    sigma_target_sq = F.conv2d(target * target, window, padding=pad, groups=channels) - mu_target_sq
    sigma_pred_target = F.conv2d(pred * target, window, padding=pad, groups=channels) - mu_pred_target

    c1 = (0.01 * data_range) ** 2
    c2 = (0.03 * data_range) ** 2

    numerator = (2 * mu_pred_target + c1) * (2 * sigma_pred_target + c2)
    denominator = (mu_pred_sq + mu_target_sq + c1) * (sigma_pred_sq + sigma_target_sq + c2)
    ssim_map = numerator / denominator
    return ssim_map.mean().item()
