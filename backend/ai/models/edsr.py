"""A lightweight EDSR-style residual CNN for satellite-imagery super-resolution.

    Input (N, in_channels, H, W)
          |
          v
    Shallow feature extraction (one 3x3 conv)
          |
          v
    N x ResidualBlock (conv -> ReLU -> conv, residual-scaled, added back)
          |
          v
    Feature reconstruction (one 3x3 conv) + long skip from shallow features
          |
          v
    Learned upsampling (PixelShuffle, scale_factor 2 or 4)
          |
          v
    Output reconstruction (one 3x3 conv back to in_channels)
          |
          v
    Output (N, in_channels, H*scale, W*scale)

This intentionally omits EDSR's batch-norm removal debate, mean-shift RGB
normalization, and 32-block/256-feature "full" configuration — those are
tuned for 8-bit natural-image DIV2K, not 16-bit multi-band satellite
reflectance. What's kept is the part of EDSR that matters for a first,
honest, trainable satellite SR baseline: residual blocks with a small
residual scaling factor for training stability, and pixel-shuffle
upsampling (no dead-simple bicubic anywhere in the learned path).
"""

import torch
from torch import nn


class ResidualBlock(nn.Module):
    def __init__(self, num_features: int, residual_scale: float = 0.1) -> None:
        super().__init__()
        self.conv1 = nn.Conv2d(num_features, num_features, kernel_size=3, padding=1)
        self.relu = nn.ReLU(inplace=True)
        self.conv2 = nn.Conv2d(num_features, num_features, kernel_size=3, padding=1)
        self.residual_scale = residual_scale

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        residual = self.conv2(self.relu(self.conv1(x)))
        return x + residual * self.residual_scale


class PixelShuffleUpsampler(nn.Module):
    """Supports scale_factor 2 or 4 (4 = two cascaded 2x stages, the
    standard EDSR approach — avoids needing a 4x-specific conv kernel)."""

    def __init__(self, num_features: int, scale_factor: int) -> None:
        super().__init__()
        if scale_factor not in (2, 4):
            raise ValueError(f"Unsupported scale_factor for PixelShuffleUpsampler: {scale_factor}")

        stages = [2, 2] if scale_factor == 4 else [2]
        layers: list[nn.Module] = []
        for stage_scale in stages:
            layers.append(nn.Conv2d(num_features, num_features * stage_scale**2, kernel_size=3, padding=1))
            layers.append(nn.PixelShuffle(stage_scale))
        self.net = nn.Sequential(*layers)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.net(x)


class EDSRLite(nn.Module):
    """Configurable lightweight EDSR variant.

    Parameters intentionally mirror the env-var names documented in
    backend/.env.example (MODEL_NAME=edsr_satellite, SCALE_FACTOR,
    NUM_CHANNELS, NUM_FEATURES, NUM_RES_BLOCKS) so a checkpoint's saved
    config maps directly onto these constructor arguments.
    """

    def __init__(
        self,
        in_channels: int = 3,
        num_features: int = 64,
        num_res_blocks: int = 8,
        scale_factor: int = 2,
        residual_scale: float = 0.1,
    ) -> None:
        super().__init__()
        self.in_channels = in_channels
        self.num_features = num_features
        self.num_res_blocks = num_res_blocks
        self.scale_factor = scale_factor

        self.shallow_extract = nn.Conv2d(in_channels, num_features, kernel_size=3, padding=1)
        self.res_blocks = nn.Sequential(
            *[ResidualBlock(num_features, residual_scale) for _ in range(num_res_blocks)]
        )
        self.reconstruct = nn.Conv2d(num_features, num_features, kernel_size=3, padding=1)
        self.upsample = PixelShuffleUpsampler(num_features, scale_factor)
        self.output_conv = nn.Conv2d(num_features, in_channels, kernel_size=3, padding=1)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        shallow = self.shallow_extract(x)
        deep = self.reconstruct(self.res_blocks(shallow))
        features = shallow + deep  # long skip connection, standard EDSR
        upsampled = self.upsample(features)
        return self.output_conv(upsampled)

    def config(self) -> dict:
        """Everything needed to reconstruct this exact architecture from a
        checkpoint — see ai/training/checkpoint.py."""
        return {
            "model_name": "edsr_satellite",
            "in_channels": self.in_channels,
            "num_features": self.num_features,
            "num_res_blocks": self.num_res_blocks,
            "scale_factor": self.scale_factor,
        }

    @classmethod
    def from_config(cls, config: dict) -> "EDSRLite":
        return cls(
            in_channels=config["in_channels"],
            num_features=config["num_features"],
            num_res_blocks=config["num_res_blocks"],
            scale_factor=config["scale_factor"],
        )

    def count_parameters(self) -> int:
        return sum(p.numel() for p in self.parameters() if p.requires_grad)
