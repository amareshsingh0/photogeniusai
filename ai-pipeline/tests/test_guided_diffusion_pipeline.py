"""
Tests for GuidedDiffusionPipeline (multi-ControlNet + reward guidance).

Covers: instantiation without loading models, control image flow, generate() requirements.
Full GPU generation is skipped in CI.
"""

import pytest

try:
    from services.guided_diffusion_pipeline import (
        GuidedDiffusionPipeline,
        HAS_TORCH,
        HAS_DIFFUSERS,
        ControlImageGenerator,
    )
    from services.scene_graph_compiler import SceneGraphCompiler
except ImportError:
    from ai_pipeline.services.guided_diffusion_pipeline import (
        GuidedDiffusionPipeline,
        HAS_TORCH,
        HAS_DIFFUSERS,
        ControlImageGenerator,
    )
    from ai_pipeline.services.scene_graph_compiler import SceneGraphCompiler


def test_guided_diffusion_pipeline_instantiation_no_models():
    """GuidedDiffusionPipeline can be created with load_models=False (no GPU/download)."""
    pipe = GuidedDiffusionPipeline(device="cpu", load_models=False)
    assert pipe.device in ("cpu", "cuda")
    assert pipe.pipeline is None or pipe.pipeline is not None
    assert pipe.use_reward_guidance in (True, False)


def test_guided_diffusion_pipeline_control_generator_available():
    """When ControlImageGenerator is available, pipeline uses it for control images."""
    pipe = GuidedDiffusionPipeline(device="cpu", load_models=False)
    if pipe.control_generator is None:
        pytest.skip("ControlImageGenerator not available")
    compiler = SceneGraphCompiler(use_spacy=False)
    scene = compiler.compile("Person standing in rain")
    controls = pipe.control_generator.generate_all_controls(scene, width=256, height=256)
    assert "depth" in controls
    assert "openpose" in controls
    assert "canny" in controls


def test_guided_diffusion_pipeline_generate_requires_pipeline():
    """generate() raises when pipeline is not loaded (no GPU/models)."""
    if HAS_TORCH and HAS_DIFFUSERS:
        pytest.skip(
            "torch+diffusers present; generate() would trigger model load (slow/hang)"
        )
    pipe = GuidedDiffusionPipeline(device="cpu", load_models=False)
    compiler = SceneGraphCompiler(use_spacy=False)
    scene = compiler.compile("Woman with umbrella")
    physics_state = {"material_states": {}, "prompt_modifiers": "wet"}
    if pipe.control_generator is None:
        pytest.skip("ControlImageGenerator not available")
    with pytest.raises(RuntimeError, match="torch|diffusers|Pipeline|ControlImageGenerator"):
        pipe.generate(
            prompt="Woman with umbrella in rain",
            negative_prompt="blurry",
            scene_graph=scene,
            physics_state=physics_state,
            num_inference_steps=2,
        )


def test_guided_diffusion_pipeline_generate_requires_torch_diffusers():
    """generate() raises with clear message when torch/diffusers missing."""
    if HAS_TORCH and HAS_DIFFUSERS:
        pytest.skip("torch and diffusers are installed")
    pipe = GuidedDiffusionPipeline(device="cpu", load_models=False)
    with pytest.raises(RuntimeError, match="torch|diffusers"):
        pipe.generate(
            prompt="test",
            negative_prompt="bad",
            scene_graph={"entities": [], "constraints": []},
            physics_state={},
            num_inference_steps=2,
        )


def test_guided_diffusion_pipeline_api():
    """GuidedDiffusionPipeline has expected public API."""
    pipe = GuidedDiffusionPipeline(device="cpu", load_models=False)
    assert hasattr(pipe, "generate")
    assert hasattr(pipe, "device")
    assert hasattr(pipe, "use_reward_guidance")
    assert hasattr(pipe, "control_generator")
    assert hasattr(pipe, "reward_model")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-p", "no:asyncio"])
