"""Model construction / forward-pass tests — no network, no dataset, no
checkpoint. `pytest.importorskip` means these skip cleanly (not error) on a
machine without torch installed, so they never threaten the "39 existing
tests still pass" baseline from Phases 3-5.
"""

import pytest

torch = pytest.importorskip("torch")

from ai.models.edsr import EDSRLite  # noqa: E402


def test_model_forward_pass_shape_2x():
    model = EDSRLite(in_channels=3, num_features=16, num_res_blocks=2, scale_factor=2)
    x = torch.rand(2, 3, 32, 32)
    out = model(x)
    assert out.shape == (2, 3, 64, 64)


def test_model_forward_pass_shape_4x():
    model = EDSRLite(in_channels=3, num_features=16, num_res_blocks=2, scale_factor=4)
    x = torch.rand(1, 3, 16, 16)
    out = model(x)
    assert out.shape == (1, 3, 64, 64)


def test_model_respects_configured_channel_count():
    model = EDSRLite(in_channels=10, num_features=8, num_res_blocks=1, scale_factor=2)
    x = torch.rand(1, 10, 8, 8)
    out = model(x)
    assert out.shape == (1, 10, 16, 16)


def test_model_rejects_unsupported_scale_factor():
    with pytest.raises(ValueError):
        EDSRLite(scale_factor=3)


def test_model_config_round_trip():
    model = EDSRLite(in_channels=3, num_features=32, num_res_blocks=4, scale_factor=2)
    config = model.config()
    rebuilt = EDSRLite.from_config(config)
    assert rebuilt.config() == config


def test_model_has_learnable_parameters():
    """Guards against the model ever degenerating into a no-op wrapper
    around interpolation — it must have real trainable weights."""
    model = EDSRLite(num_features=16, num_res_blocks=2)
    assert model.count_parameters() > 1000


def test_model_output_is_not_a_trivial_passthrough():
    """A real conv stack with random init should not just reproduce a
    bicubic-upsampled input — a cheap sanity check against the '‌use
    interpolation and call it the model' failure mode this phase forbids."""
    import torch.nn.functional as F

    model = EDSRLite(in_channels=3, num_features=16, num_res_blocks=2, scale_factor=2)
    model.eval()
    x = torch.rand(1, 3, 16, 16)
    with torch.no_grad():
        model_out = model(x)
        bicubic_out = F.interpolate(x, scale_factor=2, mode="bicubic", align_corners=False)
    assert not torch.allclose(model_out, bicubic_out, atol=1e-3)


def test_gradients_flow_to_all_parameters():
    """Proves this is a real trainable network, not a frozen/dead graph."""
    model = EDSRLite(num_features=8, num_res_blocks=2)
    x = torch.rand(1, 3, 16, 16, requires_grad=True)
    target = torch.rand(1, 3, 32, 32)
    loss = torch.nn.functional.l1_loss(model(x), target)
    loss.backward()
    for name, param in model.named_parameters():
        assert param.grad is not None, f"no gradient reached {name}"
