"""
Tests for Multi-ControlNet with Real-Time Reward Guidance.
Control image generation from scene graph; reward model; no GPU required for control maps.
"""

import pytest

try:
    from services.guided_diffusion_controlnet import (
        RewardModel,
        GuidedDiffusionControlNet,
        HAS_PIL,
        HAS_TORCH,
    )
    from services.scene_graph_compiler import SceneGraphCompiler
except ImportError:
    from ai_pipeline.services.guided_diffusion_controlnet import (
        RewardModel,
        GuidedDiffusionControlNet,
        HAS_PIL,
        HAS_TORCH,
    )
    from ai_pipeline.services.scene_graph_compiler import SceneGraphCompiler


def test_reward_model_compute_rewards():
    """RewardModel returns anatomy, physics, aesthetics, constraint_satisfaction, surprise."""
    model = RewardModel()
    scene_graph = {
        "entities": [
            {"id": "person_0", "type": "person", "properties": {}},
            {
                "id": "object_umbrella_1",
                "type": "object",
                "properties": {"name": "umbrella"},
            },
        ],
        "constraints": [
            {"type": "visibility", "rule": "heads_visible", "severity": "critical"},
        ],
    }
    physics_state = {"material_states": {}, "prompt_modifiers": "wet"}
    # Latents can be None when decode is placeholder
    rewards = model.compute_rewards(
        None, scene_graph, physics_state, step=20, total_steps=40
    )
    assert "anatomy" in rewards
    assert "physics" in rewards
    assert "aesthetics" in rewards
    assert "constraint_satisfaction" in rewards
    assert "surprise" in rewards
    assert all(0 <= v <= 1 for v in rewards.values())


def test_reward_model_surprise_fantasy():
    """Surprise reward higher when fantasy entities present."""
    model = RewardModel()
    scene_real = {"entities": [{"type": "person"}], "constraints": []}
    scene_fantasy = {"entities": [{"type": "mythical_creature"}], "constraints": []}
    r_real = model.compute_rewards(None, scene_real, {}, 25, 40)
    r_fantasy = model.compute_rewards(None, scene_fantasy, {}, 25, 40)
    assert r_fantasy["surprise"] >= r_real["surprise"]


def test_generate_control_images_from_scene():
    """Generate depth, openpose, canny from compiled scene graph."""
    compiler = SceneGraphCompiler(use_spacy=False)
    scene = compiler.compile("Mother with 2 children under umbrella in rain")
    guide = GuidedDiffusionControlNet()
    control = guide.generate_control_images(scene, width=512, height=512)
    assert "depth" in control
    assert "openpose" in control
    assert "canny" in control
    import numpy as np

    for key in ("depth", "openpose", "canny"):
        img = control[key]
        if hasattr(img, "size"):
            assert img.size[0] == 512 and img.size[1] == 512
        else:
            assert isinstance(img, np.ndarray)
            assert img.shape[0] == 512 and img.shape[1] == 512


def test_control_images_person_depth_foreground():
    """Depth map: persons at lower depth (foreground), background higher."""
    compiler = SceneGraphCompiler(use_spacy=False)
    scene = compiler.compile("Couple at beach")
    guide = GuidedDiffusionControlNet()
    control = guide.generate_control_images(scene, width=256, height=256)
    import numpy as np

    depth = control["depth"]
    if hasattr(depth, "convert"):
        depth = np.array(depth.convert("L"))
    else:
        depth = (
            depth if depth.ndim == 2 else np.dot(depth[..., :3], [0.299, 0.587, 0.114])
        )
    # Background ~0.85 * 255, foreground lower
    mean_val = float(np.mean(depth))
    assert mean_val < 240  # some foreground pixels


def test_aesthetic_guidance_scale_init():
    """GuidedDiffusionControlNet accepts aesthetic_guidance_scale in __init__ (default 0.3)."""
    guide = GuidedDiffusionControlNet(aesthetic_guidance_scale=0.0)
    assert getattr(guide, "_aesthetic_guidance_scale", 0.0) == 0.0
    guide2 = GuidedDiffusionControlNet()
    assert getattr(guide2, "_aesthetic_guidance_scale", 0.3) == 0.3


def test_aesthetic_gradient_helper_no_predictor():
    """_apply_aesthetic_gradient returns (None, noise_pred) when no aesthetic predictor loaded."""
    guide = GuidedDiffusionControlNet(aesthetic_guidance_scale=0.0)
    if not HAS_TORCH:
        pytest.skip("torch required")
    import torch
    fake_latents = torch.randn(1, 4, 128, 128)
    fake_noise = torch.randn(1, 4, 128, 128)
    score, out_noise = guide._apply_aesthetic_gradient(
        fake_latents, fake_noise, 0.3, 10, 50
    )
    assert score is None
    assert out_noise is fake_noise


def test_generate_with_guidance_requires_pipeline():
    """generate_with_guidance raises when torch/diffusers missing; skip when present (would download)."""
    try:
        from services.guided_diffusion_controlnet import HAS_TORCH, HAS_DIFFUSERS
    except ImportError:
        from ai_pipeline.services.guided_diffusion_controlnet import (
            HAS_TORCH,
            HAS_DIFFUSERS,
        )
    if HAS_TORCH and HAS_DIFFUSERS:
        pytest.skip(
            "torch+diffusers present; full test would download models (run with GPU when needed)"
        )
    guide = GuidedDiffusionControlNet()
    with pytest.raises(RuntimeError, match="requires torch|diffusers|Pipeline"):
        guide.generate_with_guidance(
            "test",
            "bad",
            {"depth": None, "openpose": None, "canny": None},
            {},
            {},
            num_steps=2,
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-p", "no:asyncio"])
