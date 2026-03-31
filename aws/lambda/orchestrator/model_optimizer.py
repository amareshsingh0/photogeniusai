"""
Model Optimizer – Optimize prompts for different AI models.

- Midjourney v7: Natural sentences + parameters (--ar, --stylize, --chaos, --weird, --style)
- Flux: Long descriptive paragraphs (500+ tokens OK)
- DALL-E 3: Clear paragraphs, literal, avoid over-poetic
- Stable Diffusion: Comma-separated keywords, weights (keyword:1.3), strong negatives
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING, Any, Dict, Optional

if TYPE_CHECKING:
    from services.multi_variant_generator import PromptVariant

from services.observability import StructuredLogger, trace_function

logger = StructuredLogger(__name__)


class AIModel(str, Enum):
    """Supported AI models."""

    MIDJOURNEY_V7 = "midjourney_v7"
    FLUX = "flux"
    DALLE3 = "dalle3"
    STABLE_DIFFUSION = "stable_diffusion"


@dataclass
class ModelOptimizedPrompt:
    """Prompt optimized for a specific model."""

    model: AIModel
    optimized_prompt: str
    negative_prompt: Optional[str] = None
    parameters: Optional[Dict[str, Any]] = None
    copy_ready: Optional[str] = None

    def __post_init__(self) -> None:
        if self.copy_ready is None:
            self.copy_ready = self.optimized_prompt


class ModelOptimizer:
    """Optimize prompts for different AI models."""

    MODEL_GUIDELINES = {
        AIModel.MIDJOURNEY_V7: {
            "max_length": None,
            "format": "natural_sentence",
            "supports_weights": False,
            "supports_negatives": True,
            "supports_parameters": True,
            "optimal_structure": "Subject + action + environment + style + quality, natural language",
        },
        AIModel.FLUX: {
            "max_length": 500,
            "format": "descriptive_paragraph",
            "supports_weights": False,
            "supports_negatives": False,
            "supports_parameters": False,
            "optimal_structure": "Long detailed paragraph, very specific, literal",
        },
        AIModel.DALLE3: {
            "max_length": 400,
            "format": "clear_paragraph",
            "supports_weights": False,
            "supports_negatives": False,
            "supports_parameters": False,
            "optimal_structure": "Clear paragraph, literal, avoid over-poetic",
        },
        AIModel.STABLE_DIFFUSION: {
            "max_length": 200,
            "format": "comma_separated",
            "supports_weights": True,
            "supports_negatives": True,
            "supports_parameters": False,
            "optimal_structure": "Comma-separated keywords, use weights for emphasis",
        },
    }

    @trace_function("model.optimize")  # type: ignore[misc]
    def optimize_for_model(
        self,
        prompt: str,
        negative_prompt: Optional[str],
        model: AIModel,
        model_params: Optional[Dict[str, Any]] = None,
    ) -> ModelOptimizedPrompt:
        """Optimize prompt for the given model."""
        if model == AIModel.MIDJOURNEY_V7:
            return self._optimize_for_midjourney(prompt, negative_prompt, model_params)
        if model == AIModel.FLUX:
            return self._optimize_for_flux(prompt)
        if model == AIModel.DALLE3:
            return self._optimize_for_dalle(prompt)
        if model == AIModel.STABLE_DIFFUSION:
            return self._optimize_for_sd(prompt, negative_prompt)
        return ModelOptimizedPrompt(
            model=model,
            optimized_prompt=prompt,
            negative_prompt=negative_prompt,
            copy_ready=prompt,
        )

    def _optimize_for_midjourney(
        self,
        prompt: str,
        negative_prompt: Optional[str],
        model_params: Optional[Dict[str, Any]],
    ) -> ModelOptimizedPrompt:
        """Optimize for Midjourney v7: natural sentences + --ar, --stylize, --chaos, --weird, --no."""
        params = dict(model_params) if model_params else {}
        param_parts: list[str] = []

        ar = params.get("ar", "16:9")
        param_parts.append(f"--ar {ar}")
        param_parts.append("--v 7")
        stylize = params.get("stylize", 750)
        param_parts.append(f"--stylize {stylize}")
        chaos = params.get("chaos", 40)
        if chaos > 0:
            param_parts.append(f"--chaos {chaos}")
        weird = params.get("weird", 0)
        if weird > 0:
            param_parts.append(f"--weird {weird}")
        style = params.get("style")
        if style:
            param_parts.append(f"--style {style}")
        if negative_prompt:
            key_negatives = self._extract_key_negatives(negative_prompt)
            if key_negatives:
                param_parts.append(f"--no {key_negatives}")

        param_string = " ".join(param_parts)
        full_prompt = f"{prompt} {param_string}"

        logger.info(
            "Optimized for Midjourney v7",
            param_count=len(param_parts),
            total_length=len(full_prompt),
        )
        return ModelOptimizedPrompt(
            model=AIModel.MIDJOURNEY_V7,
            optimized_prompt=prompt,
            negative_prompt=negative_prompt,
            parameters=params,
            copy_ready=full_prompt,
        )

    def _optimize_for_flux(self, prompt: str) -> ModelOptimizedPrompt:
        """Optimize for Flux: long descriptive paragraph."""
        parts = [p.strip() for p in prompt.split(",") if p.strip()]
        sentences: list[str] = []
        current: list[str] = []

        for i, part in enumerate(parts):
            current.append(part)
            if len(current) >= 3 or i == len(parts) - 1:
                sentence = ", ".join(current)
                if sentence:
                    sentence = sentence[0].upper() + sentence[1:]
                if sentence and not sentence.endswith("."):
                    sentence += "."
                sentences.append(sentence)
                current = []

        paragraph = " ".join(sentences)
        if len(paragraph) < 200:
            paragraph += (
                " The image features intricate details, realistic textures, and "
                "professional composition. The lighting is carefully crafted to enhance "
                "depth and atmosphere. Every element is rendered with meticulous "
                "attention to quality and visual appeal."
            )

        logger.info(
            "Optimized for Flux",
            original_length=len(prompt),
            optimized_length=len(paragraph),
        )
        return ModelOptimizedPrompt(
            model=AIModel.FLUX,
            optimized_prompt=paragraph,
            copy_ready=paragraph,
        )

    def _optimize_for_dalle(self, prompt: str) -> ModelOptimizedPrompt:
        """Optimize for DALL-E 3: clear, literal paragraph; avoid over-poetic."""
        parts = [p.strip() for p in prompt.split(",") if p.strip()]
        poetic_words = [
            "ethereal", "transcendent", "mystical", "otherworldly",
            "impossibly", "mind-bending", "paradoxical",
        ]
        filtered = [
            p for p in parts
            if not any(w in p.lower() for w in poetic_words)
        ]
        if not filtered:
            filtered = parts
        key_parts = filtered[:20]

        if not key_parts:
            description = "A photograph."
        else:
            description = f"A {key_parts[0]}"
            if len(key_parts) > 1:
                description += f" featuring {', '.join(key_parts[1:5])}"
            if len(key_parts) > 5:
                description += f". The scene includes {', '.join(key_parts[5:10])}"
            if len(key_parts) > 10:
                description += f". Additional details: {', '.join(key_parts[10:15])}"
            if not description.endswith("."):
                description += "."

        logger.info(
            "Optimized for DALL-E 3",
            original_parts=len(parts),
            filtered_parts=len(filtered),
            final_length=len(description),
        )
        return ModelOptimizedPrompt(
            model=AIModel.DALLE3,
            optimized_prompt=description,
            copy_ready=description,
        )

    def _optimize_for_sd(
        self,
        prompt: str,
        negative_prompt: Optional[str],
    ) -> ModelOptimizedPrompt:
        """Optimize for Stable Diffusion: comma-separated with weights and negatives."""
        parts = [p.strip() for p in prompt.split(",") if p.strip()]
        important_keywords = [
            "cinematic", "masterpiece", "best quality", "highly detailed",
            "professional", "8k", "volumetric", "dramatic",
        ]
        weighted_parts: list[str] = []
        for part in parts:
            part_lower = part.lower()
            if any(kw in part_lower for kw in important_keywords):
                weighted_parts.append(f"({part}:1.2)")
            else:
                weighted_parts.append(part)
        optimized = ", ".join(weighted_parts)

        optimized_negative: Optional[str] = None
        if negative_prompt:
            neg_parts = [p.strip() for p in negative_prompt.split(",") if p.strip()]
            key_negatives = neg_parts[:30]
            optimized_negative = ", ".join(key_negatives)

        logger.info(
            "Optimized for Stable Diffusion",
            weighted_count=sum(1 for p in weighted_parts if ":1." in p),
            total_parts=len(weighted_parts),
        )
        return ModelOptimizedPrompt(
            model=AIModel.STABLE_DIFFUSION,
            optimized_prompt=optimized,
            negative_prompt=optimized_negative,
            copy_ready=optimized,
        )

    def _extract_key_negatives(self, negative_prompt: str) -> str:
        """Extract 3–5 key negatives for MJ --no."""
        parts = [p.strip() for p in negative_prompt.split(",") if p.strip()]
        priority = [
            "blurry", "low quality", "cartoon", "anime",
            "deformed", "ugly", "bad anatomy",
        ]
        key_negs: list[str] = []
        for neg in priority:
            if any(neg in p.lower() for p in parts):
                key_negs.append(neg)
                if len(key_negs) >= 5:
                    break
        return ", ".join(key_negs) if key_negs else "blurry, low quality"


def optimize_variant_for_all_models(
    variant: "PromptVariant",
) -> Dict[AIModel, ModelOptimizedPrompt]:
    """Optimize a PromptVariant for all supported models."""
    optimizer = ModelOptimizer()
    results: Dict[AIModel, ModelOptimizedPrompt] = {}
    prompt = getattr(variant, "enhanced_prompt", "")
    negative = getattr(variant, "negative_prompt", None)
    params = getattr(variant, "model_params", None)
    for model in AIModel:
        results[model] = optimizer.optimize_for_model(
            prompt=prompt,
            negative_prompt=negative,
            model=model,
            model_params=params if model == AIModel.MIDJOURNEY_V7 else None,
        )
    return results
