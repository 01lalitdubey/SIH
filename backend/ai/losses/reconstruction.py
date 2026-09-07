"""Reconstruction losses for super-resolution training.

Starting with plain L1 (mean absolute error) rather than L2/MSE or a
perceptual/SSIM/edge/spectral-consistency loss — L1 is the standard,
well-understood baseline for SR (it produces less blur than L2 and needs
no auxiliary pretrained network, unlike perceptual loss). Per the Phase 6
brief: get the baseline working on a single, simple loss before layering
on anything fancier — that experimentation is explicitly future work, not
part of this baseline.

CharbonnierLoss is included (a differentiable smooth approximation of L1,
sqrt((x-y)^2 + eps^2)) since it's a one-line alternative sometimes used in
SR papers for a smoother gradient near zero — available but NOT the
default, so the design decision (L1) is explicit rather than implied by
"whatever happened to be imported."
"""

import torch
from torch import nn


class CharbonnierLoss(nn.Module):
    def __init__(self, eps: float = 1e-3) -> None:
        super().__init__()
        self.eps = eps

    def forward(self, pred: torch.Tensor, target: torch.Tensor) -> torch.Tensor:
        return torch.mean(torch.sqrt((pred - target) ** 2 + self.eps**2))


def get_loss(name: str = "l1") -> nn.Module:
    if name == "l1":
        return nn.L1Loss()
    if name == "charbonnier":
        return CharbonnierLoss()
    raise ValueError(f"Unknown loss '{name}'. Expected 'l1' or 'charbonnier'.")
