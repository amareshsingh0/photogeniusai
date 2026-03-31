"""
Real-Time Reward Model for Guided Diffusion.

Computes multi-objective rewards during generation to guide the diffusion process.
Rewards guide toward: correct anatomy, realistic physics, high aesthetics, constraint satisfaction, surprise elements.
P0: Multi-ControlNet with guided diffusion — Task 4.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

import numpy as np

# Optional heavy dependencies
try:
    import torch
    import torch.nn.functional as F

    HAS_TORCH = True
except ImportError:
    torch = None
    F = None
    HAS_TORCH = False

try:
    from PIL import Image

    HAS_PIL = True
except ImportError:
    Image = None
    HAS_PIL = False

try:
    from transformers import CLIPModel, CLIPProcessor

    HAS_TRANSFORMERS = True
except ImportError:
    CLIPModel = None
    CLIPProcessor = None
    HAS_TRANSFORMERS = False


def _entity_type(e: Any) -> str:
    """Get entity type from EntityNode or dict."""
    if isinstance(e, dict):
        return e.get("type", "object")
    return getattr(e, "type", "object")


def _constraint_rule(c: Any) -> str:
    if isinstance(c, dict):
        return c.get("rule", "")
    return getattr(c, "rule", "")


def _constraint_severity(c: Any) -> str:
    if isinstance(c, dict):
        return c.get("severity", "medium")
    return getattr(c, "severity", "medium")


class RewardModel:
    """
    Compute rewards during diffusion for online guidance.

    Reward Categories:
    1. Anatomy: Correct body structure, head visibility, limb count
    2. Physics: Material realism, wetness accuracy, lighting
    3. Aesthetics: Visual quality, composition, color harmony
    4. Constraint Satisfaction: Scene graph requirements met
    5. Surprise/Novelty: Creative elements that exceed expectations
    """

    def __init__(
        self,
        device: Optional[str] = None,
        load_clip: bool = True,
        load_models: Optional[bool] = None,
        **kwargs: Any,
    ) -> None:
        if load_models is not None:
            load_clip = load_clip or load_models
        self.device = device or (
            "cuda" if HAS_TORCH and torch.cuda.is_available() else "cpu"
        )
        self.clip_model = None
        self.clip_processor = None
        self.aesthetic_model = None
        self.has_aesthetic_model = False
        self._last_rewards: Optional[Dict[str, float]] = None
        self.scene_embedding_cache: Dict[str, Any] = {}

        if load_clip and HAS_TRANSFORMERS and HAS_TORCH:
            try:
                self.clip_model = CLIPModel.from_pretrained(
                    "openai/clip-vit-large-patch14"
                ).to(self.device)
                self.clip_processor = CLIPProcessor.from_pretrained(
                    "openai/clip-vit-large-patch14"
                )
            except Exception:
                pass

        try:
            if HAS_TORCH and HAS_TRANSFORMERS:
                from transformers import AutoModel

                self.aesthetic_model = AutoModel.from_pretrained(
                    "cafeai/cafe_aesthetic",
                    trust_remote_code=True,
                ).to(self.device)
                self.has_aesthetic_model = True
        except Exception:
            pass

    def compute_rewards(
        self,
        latents: Any,
        scene_graph: Dict[str, Any],
        physics_state: Dict[str, Any],
        step: int,
        total_steps: int,
        vae: Any = None,
        decode_every_n: int = 5,
    ) -> Dict[str, float]:
        """
        Compute multi-objective rewards during diffusion.

        Args:
            latents: Current latent state (before decoding)
            scene_graph: Scene structure from compiler
            physics_state: Physics simulation results
            step: Current denoising step
            total_steps: Total steps in schedule
            vae: Optional VAE decoder for latent→image (when provided, decode for reward)
            decode_every_n: Decode latents every N steps when vae provided (for efficiency)

        Returns:
            anatomy, physics, aesthetics, constraint_satisfaction, surprise, overall (0.0–1.0)
        """
        neutral = {
            "anatomy": 0.5,
            "physics": 0.5,
            "aesthetics": 0.5,
            "constraint_satisfaction": 0.5,
            "surprise": 0.5,
            "overall": 0.5,
        }

        if not HAS_PIL:
            return neutral

        if step < total_steps * 0.2:
            return neutral

        preview_image = None
        if vae is not None and HAS_TORCH and step % decode_every_n == 0:
            try:
                preview_image = self._decode_latents(latents, vae)
            except Exception:
                pass
        if preview_image is None:
            preview_image = self._decode_latents_fast(latents)

        if preview_image is None:
            if self._last_rewards is not None:
                return dict(self._last_rewards)
            return neutral

        rewards: Dict[str, float] = {}

        rewards["anatomy"] = self._compute_anatomy_reward(
            preview_image, scene_graph, step, total_steps
        )
        rewards["physics"] = self._compute_physics_reward(
            preview_image, physics_state, step, total_steps
        )
        rewards["aesthetics"] = self._compute_aesthetic_reward(preview_image)
        rewards["constraint_satisfaction"] = self._compute_constraint_reward(
            preview_image, scene_graph
        )
        rewards["surprise"] = self._compute_surprise_reward(preview_image, scene_graph)

        rewards["overall"] = (
            rewards["anatomy"] * 0.30
            + rewards["physics"] * 0.20
            + rewards["aesthetics"] * 0.25
            + rewards["constraint_satisfaction"] * 0.15
            + rewards["surprise"] * 0.10
        )

        self._last_rewards = rewards
        return rewards

    def _decode_latents(self, latents: Any, vae: Any) -> Optional[Any]:
        """Decode latents to preview image (low-precision for speed)."""
        if not HAS_TORCH or not HAS_PIL or torch is None:
            return None
        try:
            with torch.no_grad():
                scaling = getattr(getattr(vae, "config", None), "scaling_factor", 1.0)
                if scaling != 1.0:
                    latents = latents / scaling
                out = vae.decode(latents, return_dict=False)
                image = out[0] if out else None
                if image is None:
                    return None
                image = (image / 2 + 0.5).clamp(0, 1)
                image = image.cpu().permute(0, 2, 3, 1).numpy()[0]
                image = (image * 255).astype(np.uint8)
                return Image.fromarray(image)
        except Exception:
            return None

    def _decode_latents_fast(self, latents: Any) -> Optional[Any]:
        """Placeholder when no VAE; return gray image for CLIP fallback."""
        if not HAS_PIL:
            return None
        return Image.new("RGB", (512, 512), color="gray")

    def _compute_anatomy_reward(
        self,
        image: Any,
        scene_graph: Dict[str, Any],
        step: int,
        total_steps: int,
    ) -> float:
        """Reward correct anatomy (expected people count, visible heads)."""
        quality = scene_graph.get("quality_requirements") or {}
        expected_people = quality.get("person_count_exact", 0)

        if expected_people == 0:
            return 1.0

        if self.clip_model is None or self.clip_processor is None or not HAS_TORCH:
            return 0.7

        try:
            texts = [
                f"photo of exactly {expected_people} people",
                f"photo of {expected_people} complete human figures with visible heads",
                "photo of people with correct anatomy",
            ]
            inputs = self.clip_processor(
                text=texts,
                images=image,
                return_tensors="pt",
                padding=True,
            ).to(self.device)

            with torch.no_grad():
                outputs = self.clip_model(**inputs)
                logits = getattr(outputs, "logits_per_image", None)
                if logits is None:
                    return 0.7
                probs = logits.softmax(dim=1)[0]
            score = float(probs.mean().item())

            progress = step / max(total_steps, 1)
            if progress > 0.7:
                score = min(1.0, score**2)
            return float(np.clip(score, 0.0, 1.0))
        except Exception:
            return 0.7

    def _compute_physics_reward(
        self,
        image: Any,
        physics_state: Dict[str, Any],
        step: int,
        total_steps: int,
    ) -> float:
        """Reward physically plausible rendering (wetness, lighting, materials)."""
        if not physics_state or "prompt_modifiers" not in physics_state:
            return 0.7

        prompt_mods = (physics_state.get("prompt_modifiers") or "").lower()
        checks = []

        if "wet" in prompt_mods or "rain" in prompt_mods:
            s = self._clip_similarity(
                image,
                "photo with visible wet surfaces, water droplets, and moisture",
            )
            checks.append(s)
        if "night" in prompt_mods or "dark" in prompt_mods:
            s = self._clip_similarity(
                image,
                "nighttime photo with low lighting and dramatic shadows",
            )
            checks.append(s)
        elif "golden hour" in prompt_mods:
            s = self._clip_similarity(
                image,
                "photo with warm golden hour lighting",
            )
            checks.append(s)
        if "glow" in prompt_mods or "ethereal" in prompt_mods:
            s = self._clip_similarity(
                image,
                "photo with magical glowing effects and ethereal atmosphere",
            )
            checks.append(s)

        if checks:
            return float(np.mean(checks))
        return 0.7

    def _compute_aesthetic_reward(self, image: Any) -> float:
        """Reward visual quality (aesthetic model or CLIP fallback)."""
        if (
            self.has_aesthetic_model
            and self.aesthetic_model is not None
            and image is not None
        ):
            try:
                score = getattr(self.aesthetic_model, "predict", lambda x: 5.0)(image)
                return float(np.clip(score / 10.0, 0.0, 1.0))
            except Exception:
                pass

        prompts = [
            "beautiful professional photograph",
            "high quality award winning photo",
            "stunning cinematic image",
            "masterpiece photograph",
        ]
        scores = [self._clip_similarity(image, p) for p in prompts]
        return float(np.mean(scores)) if scores else 0.5

    def _compute_constraint_reward(
        self, image: Any, scene_graph: Dict[str, Any]
    ) -> float:
        """Reward satisfaction of scene graph constraints."""
        constraints = scene_graph.get("constraints", [])
        if not constraints:
            return 0.8

        critical = [c for c in constraints if _constraint_severity(c) == "critical"]
        if not critical:
            return 0.8

        descs = []
        for c in critical[:3]:
            rule = _constraint_rule(c).replace("_", " ")
            if rule:
                descs.append(f"photo with {rule}")
        if not descs:
            return 0.7
        scores = [self._clip_similarity(image, d) for d in descs]
        return float(np.mean(scores))

    def _compute_surprise_reward(
        self, image: Any, scene_graph: Dict[str, Any]
    ) -> float:
        """Reward novel, surprising elements (fantasy/realistic)."""
        entities = scene_graph.get("entities", [])
        has_fantasy = any(
            _entity_type(e)
            in ("mythical_creature", "magical_object", "imaginative_structure")
            for e in entities
        )

        if has_fantasy:
            prompts = [
                "creative imaginative artwork",
                "surprising unique composition",
                "fantastical dreamlike scene",
                "visually striking unusual image",
            ]
        else:
            prompts = [
                "professionally composed photograph",
                "interesting unique perspective",
                "visually engaging scene",
            ]
        scores = [self._clip_similarity(image, p) for p in prompts]
        base = float(np.mean(scores))
        return base if has_fantasy else base * 0.8

    def _clip_similarity(self, image: Any, text: str) -> float:
        """CLIP similarity between image and text; returns 0.0–1.0."""
        if self.clip_model is None or self.clip_processor is None or not HAS_TORCH:
            return 0.5
        try:
            inputs = self.clip_processor(
                text=[text],
                images=image,
                return_tensors="pt",
                padding=True,
            ).to(self.device)

            with torch.no_grad():
                outputs = self.clip_model(**inputs)
                image_embeds = outputs.image_embeds
                text_embeds = outputs.text_embeds
                image_embeds = image_embeds / image_embeds.norm(dim=-1, keepdim=True)
                text_embeds = text_embeds / text_embeds.norm(dim=-1, keepdim=True)
                similarity = (image_embeds @ text_embeds.T).item()

            return float((similarity + 1.0) / 2.0)
        except Exception:
            return 0.5
