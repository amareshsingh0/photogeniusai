"""
Smart Generation Config System.

Intelligent parameter configuration for image generation: auto-selects optimal
steps, guidance, scheduler, and aspect ratio based on prompt domain, complexity,
and quality requirements. Supports presets, validation, and performance metrics.
"""

from __future__ import annotations

import importlib.util
import logging
import os
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

# Optional observability
_logger = logging.getLogger(__name__)
_observability = None
StructuredLogger = None
trace_function = lambda n=None: (lambda f: f)  # type: ignore[assignment, misc]

try:
    this_dir = os.path.dirname(os.path.abspath(__file__))
    _path = os.path.join(this_dir, "observability.py")
    if os.path.isfile(_path):
        spec = importlib.util.spec_from_file_location("observability", _path)
        if spec and spec.loader:
            _observability = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(_observability)
            StructuredLogger = getattr(_observability, "StructuredLogger", None)
            trace_function = getattr(_observability, "trace_function", trace_function)
except Exception:
    pass
if StructuredLogger is None:
    try:
        from services.observability import StructuredLogger, trace_function  # type: ignore[assignment]
    except Exception:
        pass


def _log():
    logger_cls = StructuredLogger
    if logger_cls is not None:
        return logger_cls(__name__)
    return _logger


# ==================== Enums ====================


class GenerationQuality(str, Enum):
    """Quality/speed tradeoff presets."""

    FAST = "fast"           # 20 steps, fast preview
    BALANCED = "balanced"   # 30 steps, good quality
    QUALITY = "quality"     # 50 steps, best results
    ULTRA = "ultra"         # 75+ steps, maximum detail


class Scheduler(str, Enum):
    """Available samplers/schedulers."""

    EULER_A = "euler_a"             # Fast, good for most
    DPM_2M_KARRAS = "dpm_2m_karras"  # High quality
    DDIM = "ddim"                    # Stable, deterministic
    PNDM = "pndm"                    # Fast convergence
    UNIPC = "unipc"                  # Fast + quality


# ==================== GenerationConfig ====================


@dataclass
class GenerationConfig:
    """Complete generation parameters."""

    # Core parameters
    steps: int = 30
    guidance_scale: float = 7.5
    scheduler: Scheduler = Scheduler.EULER_A

    # Image specs
    width: int = 1024
    height: int = 1024
    aspect_ratio: Optional[str] = None  # "16:9", "1:1", etc.

    # Quality controls
    quality_preset: GenerationQuality = GenerationQuality.BALANCED
    clip_skip: int = 1

    # Advanced
    seed: Optional[int] = None
    num_images: int = 1

    # Model-specific
    model_params: Dict[str, Any] = field(default_factory=dict)

    # Metadata
    auto_detected: bool = False
    reasoning: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Export config to dict for API/serialization."""
        return {
            "steps": self.steps,
            "guidance_scale": self.guidance_scale,
            "scheduler": self.scheduler.value,
            "width": self.width,
            "height": self.height,
            "aspect_ratio": self.aspect_ratio,
            "quality_preset": self.quality_preset.value,
            "clip_skip": self.clip_skip,
            "seed": self.seed,
            "num_images": self.num_images,
            "model_params": self.model_params,
            "auto_detected": self.auto_detected,
            "reasoning": self.reasoning,
        }


# ==================== SmartConfigBuilder ====================


class SmartConfigBuilder:
    """Intelligently build generation configs from prompts and presets."""

    # Quality preset definitions
    QUALITY_PRESETS: Dict[GenerationQuality, Dict[str, Any]] = {
        GenerationQuality.FAST: {
            "steps": 20,
            "guidance_scale": 7.0,
            "scheduler": Scheduler.EULER_A,
            "description": "Quick preview, lower quality",
        },
        GenerationQuality.BALANCED: {
            "steps": 30,
            "guidance_scale": 7.5,
            "scheduler": Scheduler.DPM_2M_KARRAS,
            "description": "Good balance of speed and quality",
        },
        GenerationQuality.QUALITY: {
            "steps": 50,
            "guidance_scale": 8.0,
            "scheduler": Scheduler.DPM_2M_KARRAS,
            "description": "High quality, slower generation",
        },
        GenerationQuality.ULTRA: {
            "steps": 75,
            "guidance_scale": 8.5,
            "scheduler": Scheduler.DPM_2M_KARRAS,
            "description": "Maximum detail, very slow",
        },
    }

    # Aspect ratio presets (width, height)
    ASPECT_RATIOS: Dict[str, Tuple[int, int]] = {
        "1:1": (1024, 1024),   # Square
        "16:9": (1344, 768),   # Landscape wide
        "4:3": (1152, 896),    # Landscape standard
        "3:4": (896, 1152),    # Portrait standard
        "9:16": (768, 1344),   # Portrait tall
        "21:9": (1536, 640),  # Ultra wide
    }

    @trace_function("config.auto_build")  # type: ignore[misc]
    def auto_build_config(
        self,
        prompt: str,
        domain: Optional[str] = None,
        quality_override: Optional[GenerationQuality] = None,
    ) -> GenerationConfig:
        """
        Auto-detect optimal config from prompt.

        Args:
            prompt: Enhanced prompt text
            domain: Optional domain hint (e.g. "image")
            quality_override: Force specific quality preset

        Returns:
            Optimized GenerationConfig
        """
        reasoning: List[str] = []

        # Step 1: Determine quality preset
        if quality_override is not None:
            quality = quality_override
            reasoning.append(f"Quality manually set to {quality.value}")
        else:
            quality = self._detect_quality_need(prompt)
            reasoning.append(f"Auto-detected {quality.value} quality")

        preset = self.QUALITY_PRESETS[quality]

        # Step 2: Detect aspect ratio
        aspect_ratio, dimensions = self._detect_aspect_ratio(prompt, domain)
        reasoning.append(f"Aspect ratio: {aspect_ratio}")

        # Step 3: Fine-tune parameters based on prompt analysis
        guidance = preset["guidance_scale"]
        steps = preset["steps"]
        scheduler = preset["scheduler"]

        # Adjust guidance for portraits (tighter control)
        if domain == "image" and any(
            word in (prompt or "").lower()
            for word in ["portrait", "face", "person", "headshot"]
        ):
            guidance += 0.5
            reasoning.append("Increased guidance for portrait")

        # Adjust steps for complex scenes
        if any(
            word in (prompt or "").lower()
            for word in ["intricate", "detailed", "complex", "elaborate"]
        ):
            steps = int(steps * 1.2)
            reasoning.append("Increased steps for complexity")

        config = GenerationConfig(
            steps=min(steps, 100),
            guidance_scale=min(guidance, 15.0),
            scheduler=scheduler,
            width=dimensions[0],
            height=dimensions[1],
            aspect_ratio=aspect_ratio,
            quality_preset=quality,
            auto_detected=True,
            reasoning=reasoning,
        )

        _log().info(
            "Auto-built generation config",
            extra={
                "quality": quality.value,
                "steps": config.steps,
                "guidance": config.guidance_scale,
                "aspect": aspect_ratio,
                "reasoning_count": len(reasoning),
            },
        )
        return config

    def _detect_quality_need(self, prompt: str) -> GenerationQuality:
        """Detect quality requirement from prompt."""
        prompt_lower = (prompt or "").lower()

        ultra_keywords = [
            "masterpiece", "8k", "ultra detailed", "maximum quality",
            "professional photography", "award winning",
        ]
        if any(kw in prompt_lower for kw in ultra_keywords):
            return GenerationQuality.ULTRA

        quality_keywords = [
            "highly detailed", "photorealistic", "professional",
            "intricate", "cinematic",
        ]
        if any(kw in prompt_lower for kw in quality_keywords):
            return GenerationQuality.QUALITY

        fast_keywords = [
            "quick", "sketch", "draft", "preview", "rough",
        ]
        if any(kw in prompt_lower for kw in fast_keywords):
            return GenerationQuality.FAST

        return GenerationQuality.BALANCED

    def _detect_aspect_ratio(
        self,
        prompt: str,
        domain: Optional[str],
    ) -> Tuple[str, Tuple[int, int]]:
        """
        Detect optimal aspect ratio from prompt.

        Returns:
            (aspect_ratio_string, (width, height))
        """
        prompt_lower = (prompt or "").lower()

        portrait_keywords = [
            "portrait", "headshot", "face", "person standing",
            "full body", "selfie",
        ]
        if any(kw in prompt_lower for kw in portrait_keywords):
            return "3:4", self.ASPECT_RATIOS["3:4"]

        landscape_keywords = [
            "landscape", "panorama", "wide shot", "cityscape",
            "horizon", "vista", "scenery",
        ]
        if any(kw in prompt_lower for kw in landscape_keywords):
            return "16:9", self.ASPECT_RATIOS["16:9"]

        ultrawide_keywords = [
            "ultra wide", "panoramic", "cinematic wide",
        ]
        if any(kw in prompt_lower for kw in ultrawide_keywords):
            return "21:9", self.ASPECT_RATIOS["21:9"]

        return "1:1", self.ASPECT_RATIOS["1:1"]

    def build_from_preset(
        self,
        quality: GenerationQuality,
        aspect_ratio: str = "1:1",
        **overrides: Any,
    ) -> GenerationConfig:
        """Build config from preset with optional overrides."""
        preset = self.QUALITY_PRESETS[quality]
        dimensions = self.ASPECT_RATIOS.get(aspect_ratio, (1024, 1024))

        config_dict: Dict[str, Any] = {
            "steps": preset["steps"],
            "guidance_scale": preset["guidance_scale"],
            "scheduler": preset["scheduler"],
            "width": dimensions[0],
            "height": dimensions[1],
            "aspect_ratio": aspect_ratio,
            "quality_preset": quality,
        }
        # Apply overrides (only known GenerationConfig fields)
        allowed = {"steps", "guidance_scale", "scheduler", "width", "height",
                   "aspect_ratio", "quality_preset", "clip_skip", "seed",
                   "num_images", "model_params", "auto_detected", "reasoning"}
        for k, v in overrides.items():
            if k in allowed:
                config_dict[k] = v

        return GenerationConfig(**config_dict)

    def validate_config(self, config: GenerationConfig) -> bool:
        """Validate config parameters are within safe bounds."""
        issues: List[str] = []

        if config.steps < 10 or config.steps > 150:
            issues.append(f"Steps {config.steps} out of range [10, 150]")

        if config.guidance_scale < 1.0 or config.guidance_scale > 20.0:
            issues.append(
                f"Guidance {config.guidance_scale} out of range [1.0, 20.0]"
            )

        if config.width % 64 != 0 or config.height % 64 != 0:
            issues.append("Dimensions must be multiples of 64")

        if config.width > 2048 or config.height > 2048:
            issues.append("Dimensions exceed maximum 2048")

        if issues:
            _log().warning(
                "Config validation issues",
                extra={"issues": issues},
            )
            return False
        return True


# ==================== Convenience API ====================

_default_builder: Optional[SmartConfigBuilder] = None


def get_default_builder() -> SmartConfigBuilder:
    """Return the default SmartConfigBuilder instance (singleton)."""
    global _default_builder
    if _default_builder is None:
        _default_builder = SmartConfigBuilder()
    return _default_builder


def auto_build_config(
    prompt: str,
    domain: Optional[str] = None,
    quality_override: Optional[GenerationQuality] = None,
) -> GenerationConfig:
    """Convenience: auto-build config using default builder."""
    return get_default_builder().auto_build_config(
        prompt, domain=domain, quality_override=quality_override
    )


__all__ = [
    "GenerationQuality",
    "Scheduler",
    "GenerationConfig",
    "SmartConfigBuilder",
    "get_default_builder",
    "auto_build_config",
]


# ==================== Validation & Tests ====================

if __name__ == "__main__":
    builder = SmartConfigBuilder()

    # 1. Quality presets
    for q in GenerationQuality:
        cfg = builder.build_from_preset(q, "1:1")
        assert cfg.steps == builder.QUALITY_PRESETS[q]["steps"]
        assert cfg.guidance_scale == builder.QUALITY_PRESETS[q]["guidance_scale"]
        assert builder.validate_config(cfg), f"Preset {q.value} should be valid"
    print("Quality presets OK.")

    # 2. Aspect ratio detection
    ar, (w, h) = builder._detect_aspect_ratio("portrait headshot of a woman", "image")
    assert ar == "3:4"
    assert (w, h) == (896, 1152)
    ar2, (w2, h2) = builder._detect_aspect_ratio("wide landscape with mountains", None)
    assert ar2 == "16:9"
    assert (w2, h2) == (1344, 768)
    ar3, _ = builder._detect_aspect_ratio("random scene", None)
    assert ar3 == "1:1"
    print("Aspect ratio detection OK.")

    # 3. Auto-build and reasoning
    config = builder.auto_build_config(
        "professional cinematic photograph of young woman, portrait, 85mm lens",
        domain="image",
    )
    assert config.auto_detected
    assert len(config.reasoning) >= 2
    assert config.aspect_ratio == "3:4"
    assert config.guidance_scale >= 7.5
    print("Auto-build OK.")
    print("  Steps:", config.steps)
    print("  Guidance:", config.guidance_scale)
    print("  Aspect:", config.aspect_ratio)
    print("  Reasoning:", config.reasoning)

    # 4. Validation catches invalid configs
    bad = GenerationConfig(steps=5, guidance_scale=0.5, width=100, height=100)
    assert not builder.validate_config(bad)
    good = GenerationConfig(steps=30, guidance_scale=7.5, width=1024, height=1024)
    assert builder.validate_config(good)
    print("Validation OK.")

    # 5. Performance <5ms for auto_build_config
    n = 200
    t0 = time.perf_counter()
    for _ in range(n):
        builder.auto_build_config("portrait headshot", domain="image")
    elapsed_ms = (time.perf_counter() - t0) * 1000
    per_call = elapsed_ms / n
    print(f"Performance: {per_call:.3f} ms per auto_build_config ({n} calls)")
    assert per_call < 5.0, f"Auto-build should be <5ms per call, got {per_call:.3f}ms"

    # 6. Manual preset with overrides
    config2 = builder.build_from_preset(
        GenerationQuality.ULTRA,
        aspect_ratio="16:9",
        seed=42,
    )
    assert config2.quality_preset == GenerationQuality.ULTRA
    assert config2.aspect_ratio == "16:9"
    assert config2.seed == 42
    assert config2.width == 1344 and config2.height == 768
    print("build_from_preset with overrides OK.")

    # 7. Convenience API
    config3 = auto_build_config("quick sketch of a cat", quality_override=GenerationQuality.FAST)
    assert config3.quality_preset == GenerationQuality.FAST
    print("auto_build_config() convenience OK.")

    print("\nAll validation checks passed.")
    # Validation checklist:
    # [x] Quality presets work correctly
    # [x] Aspect ratio detection is accurate
    # [x] Validation catches invalid configs
    # [x] Auto-detection reasoning is clear
    # [x] Performance is fast (<5ms)
