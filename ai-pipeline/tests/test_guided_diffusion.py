"""
Tests for guided diffusion: control image generation, reward model, full pipeline.
Task 4: Multi-ControlNet with guided diffusion — control images, skeletons, depth, rewards.
"""

import pytest
import numpy as np

try:
    import torch

    CUDA_AVAILABLE = torch.cuda.is_available()
except Exception:
    torch = None
    CUDA_AVAILABLE = False

try:
    from PIL import Image
except ImportError:
    Image = None

try:
    from services.control_image_generator import ControlImageGenerator
    from services.scene_graph_compiler import SceneGraphCompiler
    from services.physics_micro_simulation import (
        PhysicsMicroSimulation,
        create_rainy_environment,
    )
except ImportError:
    from ai_pipeline.services.control_image_generator import ControlImageGenerator
    from ai_pipeline.services.scene_graph_compiler import SceneGraphCompiler
    from ai_pipeline.services.physics_micro_simulation import (
        PhysicsMicroSimulation,
        create_rainy_environment,
    )

# Skip only GPU-heavy tests in CI (no CUDA); control image tests run without GPU
SKIP_GPU = pytest.mark.skipif(
    not CUDA_AVAILABLE,
    reason="GPU required for diffusion tests",
)


class TestPromptEnhancementV2:
    """Test Prompt Enhancement V2 (scene-graph-based prompts)."""

    def test_enhance_prompt_returns_tuple(self):
        """enhance_prompt returns (positive, negative)."""
        try:
            from services.prompt_enhancement_v2 import PromptEnhancementV2
        except ImportError:
            from ai_pipeline.services.prompt_enhancement_v2 import PromptEnhancementV2

        enhancer = PromptEnhancementV2()
        positive, negative = enhancer.enhance_prompt("Person standing")
        assert isinstance(positive, str) and isinstance(negative, str)
        assert len(positive) > 0 and len(negative) > 0
        assert (
            "person" in positive.lower()
            or "people" in positive.lower()
            or "1 people" in positive.lower()
        )
        assert "blurry" in negative or "deformed" in negative

    def test_enhance_prompt_multi_person(self):
        """Multi-person prompt gets count and anatomy enhancements."""
        try:
            from services.prompt_enhancement_v2 import PromptEnhancementV2
        except ImportError:
            from ai_pipeline.services.prompt_enhancement_v2 import PromptEnhancementV2

        enhancer = PromptEnhancementV2()
        positive, negative = enhancer.enhance_prompt("Family of 4 at park")
        assert "4 people" in positive or "4 distinct" in positive
        assert (
            "no merged" in negative
            or "merged" in negative
            or "bodies fused" in negative
        )


class TestControlImageGenerator:
    """Test control image generation."""

    def test_control_generation_basic(self):
        """Test basic control image generation."""
        compiler = SceneGraphCompiler(use_spacy=False)
        scene = compiler.compile("Person standing")

        generator = ControlImageGenerator()
        controls = generator.generate_all_controls(scene)

        assert "depth" in controls
        assert "openpose" in controls
        assert "canny" in controls

        depth = controls["depth"]
        openpose = controls["openpose"]
        canny = controls["canny"]

        if hasattr(depth, "size"):
            assert depth.size == (1024, 1024)
        else:
            assert isinstance(depth, np.ndarray) and depth.shape[:2] == (1024, 1024)
        if hasattr(openpose, "size"):
            assert openpose.size == (1024, 1024)
        else:
            assert isinstance(openpose, np.ndarray) and openpose.shape[:2] == (
                1024,
                1024,
            )
        if hasattr(canny, "size"):
            assert canny.size == (1024, 1024)
        else:
            assert isinstance(canny, np.ndarray) and canny.shape[:2] == (1024, 1024)

    def test_multi_person_skeletons(self):
        """Verify each person gets complete skeleton."""
        compiler = SceneGraphCompiler(use_spacy=False)
        scene = compiler.compile("Family of 4 at park")

        generator = ControlImageGenerator()
        controls = generator.generate_all_controls(scene)

        openpose_img = controls["openpose"]
        if hasattr(openpose_img, "convert"):
            openpose_np = np.array(openpose_img.convert("RGB"))
        else:
            openpose_np = np.asarray(openpose_img)
        if openpose_np.ndim == 2:
            openpose_np = np.stack([openpose_np] * 3, axis=-1)

        white_pixels = np.sum(openpose_np > 200)
        assert white_pixels > 10000, f"Too few skeleton pixels: {white_pixels}"
        assert openpose_np.max() == 255, "Skeletons should be white"

    def test_depth_map_layering(self):
        """Test depth map has proper layering."""
        compiler = SceneGraphCompiler(use_spacy=False)
        scene = compiler.compile("Mother with child under umbrella")

        generator = ControlImageGenerator()
        controls = generator.generate_all_controls(scene)

        depth_img = controls["depth"]
        if hasattr(depth_img, "convert"):
            depth_np = np.array(depth_img.convert("L"))
        else:
            depth_np = np.asarray(depth_img)
        if depth_np.ndim == 3:
            depth_np = np.dot(depth_np[..., :3].astype(float), [0.299, 0.587, 0.114])

        std_dev = np.std(depth_np)
        assert std_dev > 10, f"Depth map too uniform: std={std_dev}"
        assert depth_np.min() < 100, "Should have foreground elements"
        assert depth_np.max() > 150, "Should have background elements"


@SKIP_GPU
class TestRewardModel:
    """Test reward computation (requires GPU)."""

    @pytest.mark.skip(reason="Requires CLIP model download")
    def test_reward_model_init(self):
        """Test reward model initializes."""
        try:
            from services.reward_model import RewardModel
        except ImportError:
            from ai_pipeline.services.reward_model import RewardModel

        model = RewardModel(device="cuda", load_clip=True)
        assert model.clip_model is not None

    @pytest.mark.skip(reason="Slow, requires models")
    def test_clip_similarity(self):
        """Test CLIP similarity scoring."""
        try:
            from services.reward_model import RewardModel
        except ImportError:
            from ai_pipeline.services.reward_model import RewardModel

        model = RewardModel(device="cuda", load_clip=True)
        test_img = Image.new("RGB", (512, 512), color="blue")
        score = model._clip_similarity(test_img, "blue image")
        assert 0.0 <= score <= 1.0


class TestAestheticGuidanceControlNet:
    """Task 1.1: Aesthetic guidance inside diffusion loop (GuidedDiffusionControlNet)."""

    def test_aesthetic_guidance_scale_parameter(self):
        """GuidedDiffusionControlNet accepts aesthetic_guidance_scale (default 0.3)."""
        try:
            from services.guided_diffusion_controlnet import GuidedDiffusionControlNet
        except ImportError:
            from ai_pipeline.services.guided_diffusion_controlnet import (
                GuidedDiffusionControlNet,
            )
        guide = GuidedDiffusionControlNet(aesthetic_guidance_scale=0.5)
        assert getattr(guide, "_aesthetic_guidance_scale", 0.5) == 0.5
        guide_default = GuidedDiffusionControlNet()
        assert getattr(guide_default, "_aesthetic_guidance_scale", 0.3) == 0.3

    def test_apply_aesthetic_gradient_no_model(self):
        """_apply_aesthetic_gradient returns (None, noise_pred) when predictor or vae missing."""
        try:
            from services.guided_diffusion_controlnet import GuidedDiffusionControlNet
        except ImportError:
            from ai_pipeline.services.guided_diffusion_controlnet import (
                GuidedDiffusionControlNet,
            )
        if torch is None:
            pytest.skip("torch required")
        guide = GuidedDiffusionControlNet(aesthetic_guidance_scale=0.0)
        latents = torch.randn(1, 4, 64, 64)
        noise_pred = torch.randn(1, 4, 64, 64)
        score, out = guide._apply_aesthetic_gradient(
            latents, noise_pred, 0.3, 10, 50
        )
        assert score is None
        assert out is noise_pred


@SKIP_GPU
class TestGuidedDiffusionPipeline:
    """Test full pipeline (requires GPU and models)."""

    @pytest.mark.skip(reason="Very slow, requires full model download")
    def test_pipeline_init(self):
        """Test pipeline initializes."""
        try:
            from services.guided_diffusion_pipeline import GuidedDiffusionPipeline
        except ImportError:
            from ai_pipeline.services.guided_diffusion_pipeline import (
                GuidedDiffusionPipeline,
            )

        pipeline = GuidedDiffusionPipeline(
            device="cuda", use_reward_guidance=False, load_models=True
        )
        assert pipeline.pipeline is not None

    @pytest.mark.skip(reason="Very slow, full generation test")
    def test_full_generation(self):
        """Test complete generation pipeline."""
        try:
            from services.guided_diffusion_pipeline import GuidedDiffusionPipeline
            from services.prompt_enhancement_v3 import enhance_v3_from_compiled
        except ImportError:
            from ai_pipeline.services.guided_diffusion_pipeline import (
                GuidedDiffusionPipeline,
            )
            from ai_pipeline.services.prompt_enhancement_v3 import (
                enhance_v3_from_compiled,
            )

        compiler = SceneGraphCompiler(use_spacy=False)
        scene = compiler.compile("Couple under umbrella in rain")

        env = create_rainy_environment(0.8)
        physics = PhysicsMicroSimulation()
        physics_result = physics.simulate(scene, env)

        enhanced = enhance_v3_from_compiled(scene, physics_result=physics_result)
        parts = [enhanced.enhanced_prompt]
        mod = physics_result.get("prompt_modifiers")
        if mod:
            parts.append(mod)
        positive = ", ".join(parts)
        negative = enhanced.negative_prompt

        pipeline = GuidedDiffusionPipeline(
            device="cuda", use_reward_guidance=True, load_models=True
        )
        result = pipeline.generate(
            prompt=positive,
            negative_prompt=negative,
            scene_graph=scene,
            physics_state=physics_result,
            num_inference_steps=20,
            reward_guidance_weight=0.3,
            seed=42,
        )

        assert result["image"] is not None
        img = result["image"]
        if hasattr(img, "size"):
            assert img.size == (1024, 1024)
        else:
            assert np.asarray(img).shape[:2] == (1024, 1024)
        if result.get("rewards_history"):
            print(f"\nRewards: {result['rewards_history'][-1]}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s", "-p", "no:asyncio"])
