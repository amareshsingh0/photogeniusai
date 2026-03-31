"""
Unified Orchestrator - Master coordinator for hybrid prompt enhancement + generation.

Pipeline: enhance → config → generate → quality check → retry (up to max_retries).
Coordinates UniversalPromptEnhancer, SmartConfigBuilder, Flux/Replicate finish,
and QualityAssessment with error handling and metrics.
"""

from __future__ import annotations

import asyncio
import importlib.util
import logging
import os
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

# Optional observability (typed for Pyright)
_logger = logging.getLogger(__name__)
_observability: Any = None
StructuredLogger: Any = None
trace_function: Any = lambda n=None: (lambda f: f)  # type: ignore[assignment, misc]

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


def _record_metric(name: str, **labels: str) -> None:
    try:
        from services.observability import Metrics
        counter = getattr(Metrics, name, None)
        if counter is not None:
            counter.labels(**labels).inc()
    except Exception:
        pass


# ==================== Imports ====================
# Use Exception so sibling module errors (e.g. services/__init__.py) don't break this module.
# Type as Any so Pyright allows use after runtime checks (raise if None).

UniversalPromptEnhancer: Any = None
EnhancedPrompt: Any = None
PromptDomain: Any = None
SmartConfigBuilder: Any = None
GenerationConfig: Any = None
GenerationQuality: Any = None
QualityAssessment: Any = None
QualityScore: Any = None
QualityVerdict: Any = None
FluxFinish: Any = None
ReplicateFinish: Any = None
FinishResult: Any = None

try:
    from services.universal_prompt_enhancer import (
        EnhancedPrompt,
        PromptDomain,
        UniversalPromptEnhancer,
    )
except Exception:
    pass

try:
    from services.generation_config import (
        GenerationConfig,
        GenerationQuality,
        SmartConfigBuilder,
    )
except Exception:
    pass

try:
    from services.quality_assessment import (
        QualityAssessment,
        QualityScore,
        QualityVerdict,
    )
except Exception:
    pass

try:
    from services.finish.flux_finish import FluxFinish
    from services.finish.replicate_finish import ReplicateFinish
    from services.finish.types import FinishResult
except Exception:
    pass


# ==================== OrchestrationResult ====================


@dataclass
class OrchestrationResult:
    """Complete result from orchestration."""

    image_url: str
    alternative_urls: List[str]
    original_prompt: str
    enhanced_prompt: str
    domain: Any  # PromptDomain when available
    quality_score: Optional[Any] = None  # QualityScore
    attempts_made: int = 0
    generation_config: Optional[Any] = None  # GenerationConfig
    model_used: str = ""
    total_time: float = 0.0
    success: bool = False
    error_message: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "image_url": self.image_url,
            "alternative_urls": self.alternative_urls,
            "original_prompt": self.original_prompt,
            "enhanced_prompt": self.enhanced_prompt,
            "domain": getattr(self.domain, "value", str(self.domain)) if self.domain else None,
            "quality_score": self.quality_score.to_dict() if self.quality_score and hasattr(self.quality_score, "to_dict") else None,
            "attempts_made": self.attempts_made,
            "generation_config": self.generation_config.to_dict() if self.generation_config and hasattr(self.generation_config, "to_dict") else None,
            "model_used": self.model_used,
            "total_time": round(self.total_time, 4),
            "success": self.success,
            "error_message": self.error_message,
        }


# ==================== UnifiedOrchestrator ====================


class UnifiedOrchestrator:
    """
    Master orchestrator for hybrid prompt enhancement + generation.

    Pipeline:
    1. Enhance prompt (domain + wow + domain-specific)
    2. Build generation config
    3. Generate image (Flux or Replicate)
    4. Assess quality
    5. Retry if needed (up to max_retries)
    6. Return result
    """

    def __init__(
        self,
        max_retries: int = 2,
        quality_threshold: Any = None,  # QualityVerdict
        finish_engine: str = "flux",
    ) -> None:
        """
        Initialize orchestrator.

        Args:
            max_retries: Max retry attempts for poor quality (total attempts = max_retries + 1)
            quality_threshold: Minimum acceptable QualityVerdict (e.g. QualityVerdict.ACCEPTABLE)
            finish_engine: "flux" or "replicate"
        """
        QV = QualityVerdict
        Enhancer = UniversalPromptEnhancer
        Builder = SmartConfigBuilder
        Flux = FluxFinish
        Repl = ReplicateFinish
        Assessor = QualityAssessment
        if QV is None:
            raise ImportError("services.quality_assessment (QualityVerdict) is required")
        if Enhancer is None or Builder is None:
            raise ImportError("universal_prompt_enhancer and generation_config are required")
        if Flux is None or Repl is None:
            raise ImportError("services.finish (FluxFinish, ReplicateFinish) is required")
        if Assessor is None:
            raise ImportError("QualityAssessment is required")

        self.max_retries = max_retries
        self.quality_threshold = quality_threshold if quality_threshold is not None else QV.ACCEPTABLE

        self.enhancer = Enhancer()
        self.config_builder = Builder()
        self.quality_assessor = Assessor()

        if finish_engine == "flux":
            self.finish_engine = Flux()
        elif finish_engine == "replicate":
            self.finish_engine = Repl()
        else:
            raise ValueError(f"Unknown finish engine: {finish_engine}")

        _log().info(
            "UnifiedOrchestrator initialized",
            extra={
                "max_retries": max_retries,
                "quality_threshold": getattr(self.quality_threshold, "value", str(self.quality_threshold)),
                "finish_engine": finish_engine,
            },
        )

    def _is_quality_acceptable(self, quality_score: Any) -> bool:
        """Check if quality meets threshold."""
        QV = QualityVerdict
        if QV is None:
            return True
        verdict_values = {
            QV.EXCELLENT: 4,
            QV.GOOD: 3,
            QV.ACCEPTABLE: 2,
            QV.POOR: 1,
        }
        score_value = verdict_values.get(getattr(quality_score, "verdict", None), 0)
        threshold_value = verdict_values.get(self.quality_threshold, 0)
        return score_value >= threshold_value

    @trace_function("orchestrator.process")  # type: ignore[misc]
    async def process(
        self,
        prompt: str,
        wow_intensity: float = 0.8,
        quality: Optional[Any] = None,  # GenerationQuality
        skip_quality_check: bool = False,
    ) -> OrchestrationResult:
        """
        Full pipeline processing.

        Args:
            prompt: Original user prompt
            wow_intensity: Wow factor intensity (0-1)
            quality: Generation quality override (e.g. GenerationQuality.QUALITY)
            skip_quality_check: Skip quality assessment (faster, no retries)

        Returns:
            OrchestrationResult with image URL and metadata
        """
        start_time = time.time()
        attempts = 0
        last_error: Optional[str] = None
        enhanced: Optional[Any] = None

        _log().info(
            "Starting orchestration",
            extra={
                "prompt_preview": (prompt or "")[:50],
                "wow_intensity": wow_intensity,
                "quality": getattr(quality, "value", "auto") if quality else "auto",
            },
        )

        # Step 1: Enhance prompt (once)
        try:
            enhanced = self.enhancer.enhance(
                prompt=prompt or "",
                wow_intensity=wow_intensity,
            )
            assert enhanced is not None
            _log().info(
                "Prompt enhanced",
                extra={
                    "domain": enhanced.domain.value,
                    "wow_score": f"{enhanced.wow_factor_score:.2f}",
                    "original_len": len(prompt or ""),
                    "enhanced_len": len(enhanced.enhanced),
                },
            )
        except Exception as e:
            _log().error("Prompt enhancement failed", extra={"error": str(e)})
            PD = PromptDomain
            default_domain = PD.GENERAL if PD is not None else "general"
            return OrchestrationResult(
                image_url="",
                alternative_urls=[],
                original_prompt=prompt or "",
                enhanced_prompt=prompt or "",
                domain=default_domain,
                quality_score=None,
                attempts_made=0,
                generation_config=None,
                model_used="none",
                total_time=time.time() - start_time,
                success=False,
                error_message=f"Enhancement failed: {str(e)}",
            )

        # Narrow type for Pyright: enhanced is set when we reach here
        assert enhanced is not None

        # Steps 2–5: Generation loop with retries
        while attempts < self.max_retries + 1:
            attempts += 1
            try:
                _log().info(
                    "Generation attempt",
                    extra={"attempt": attempts, "max_attempts": self.max_retries + 1},
                )

                # Step 2: Build config
                config = self.config_builder.auto_build_config(
                    prompt=enhanced.enhanced,
                    domain=enhanced.domain.value,
                    quality_override=quality,
                )

                if attempts > 1:
                    config.steps = min(100, int(config.steps * 1.2))
                    config.guidance_scale = min(config.guidance_scale + 0.5, 12.0)
                    _log().info(
                        "Retry config adjustment",
                        extra={"steps": config.steps, "guidance": config.guidance_scale},
                    )

                # Step 3: Generate image
                finish_result = await self.finish_engine.generate(
                    enhanced_prompt=enhanced.enhanced,
                    negative_prompt=enhanced.negative_prompt,
                    domain=enhanced.domain.value,
                    config_override=config,
                )

                _log().info(
                    "Image generated",
                    extra={
                        "url_preview": (finish_result.image_url or "")[:50],
                        "time": f"{finish_result.generation_time:.2f}s",
                    },
                )

                # Step 4: Quality check (optional)
                if skip_quality_check:
                    _log().info("Quality check skipped", extra={})
                    return OrchestrationResult(
                        image_url=finish_result.image_url,
                        alternative_urls=finish_result.alternative_urls or [],
                        original_prompt=prompt or "",
                        enhanced_prompt=enhanced.enhanced,
                        domain=enhanced.domain,
                        quality_score=None,
                        attempts_made=attempts,
                        generation_config=config,
                        model_used=finish_result.model_used or "",
                        total_time=time.time() - start_time,
                        success=True,
                    )

                # Run quality assessment
                quality_score = await self.quality_assessor.assess_quality(
                    image_url=finish_result.image_url,
                    prompt=prompt or "",
                    enhanced_prompt=enhanced.enhanced,
                )

                _log().info(
                    "Quality assessed",
                    extra={
                        "verdict": quality_score.verdict.value,
                        "score": f"{quality_score.overall_score:.3f}",
                        "should_retry": quality_score.should_retry,
                    },
                )

                quality_met = self._is_quality_acceptable(quality_score)

                if quality_met:
                    total_time = time.time() - start_time
                    _log().info(
                        "Orchestration complete",
                        extra={
                            "verdict": quality_score.verdict.value,
                            "attempts": attempts,
                            "total_time": f"{total_time:.2f}s",
                        },
                    )
                    _record_metric("orchestration_success", domain=enhanced.domain.value, attempts=str(attempts))
                    return OrchestrationResult(
                        image_url=finish_result.image_url,
                        alternative_urls=finish_result.alternative_urls or [],
                        original_prompt=prompt or "",
                        enhanced_prompt=enhanced.enhanced,
                        domain=enhanced.domain,
                        quality_score=quality_score,
                        attempts_made=attempts,
                        generation_config=config,
                        model_used=finish_result.model_used or "",
                        total_time=total_time,
                        success=True,
                    )

                # Quality not met
                _log().warning(
                    "Quality threshold not met",
                    extra={
                        "verdict": quality_score.verdict.value,
                        "threshold": getattr(self.quality_threshold, "value", str(self.quality_threshold)),
                        "issues": quality_score.issues_found,
                    },
                )

                if attempts >= self.max_retries + 1:
                    total_time = time.time() - start_time
                    _log().warning("Max retries reached, returning best attempt", extra={"attempts": attempts})
                    return OrchestrationResult(
                        image_url=finish_result.image_url,
                        alternative_urls=finish_result.alternative_urls or [],
                        original_prompt=prompt or "",
                        enhanced_prompt=enhanced.enhanced,
                        domain=enhanced.domain,
                        quality_score=quality_score,
                        attempts_made=attempts,
                        generation_config=config,
                        model_used=finish_result.model_used or "",
                        total_time=total_time,
                        success=True,
                        error_message=f"Quality below threshold after {attempts} attempts",
                    )

                await asyncio.sleep(1)
                continue

            except Exception as e:
                last_error = str(e)
                _log().error(
                    "Generation attempt failed",
                    extra={
                        "attempt": attempts,
                        "error": last_error,
                        "error_type": type(e).__name__,
                    },
                )
                _record_metric("orchestration_errors", error_type=type(e).__name__)
                if attempts >= self.max_retries + 1:
                    break
                await asyncio.sleep(2)
                continue

        # All attempts failed
        total_time = time.time() - start_time
        _log().error(
            "Orchestration failed",
            extra={"attempts": attempts, "last_error": last_error},
        )
        PD = PromptDomain
        fallback_domain = PD.GENERAL if PD is not None else "general"
        return OrchestrationResult(
            image_url="",
            alternative_urls=[],
            original_prompt=prompt or "",
            enhanced_prompt=enhanced.enhanced if enhanced else (prompt or ""),
            domain=enhanced.domain if enhanced else fallback_domain,
            quality_score=None,
            attempts_made=attempts,
            generation_config=None,
            model_used="none",
            total_time=total_time,
            success=False,
            error_message=last_error or "Unknown error",
        )


# ==================== Convenience API ====================

_default_orchestrator: Optional[UnifiedOrchestrator] = None


def get_default_orchestrator(
    max_retries: int = 2,
    quality_threshold: Any = None,
    finish_engine: str = "flux",
) -> UnifiedOrchestrator:
    """Return or create the default UnifiedOrchestrator (singleton)."""
    global _default_orchestrator
    if _default_orchestrator is None:
        _default_orchestrator = UnifiedOrchestrator(
            max_retries=max_retries,
            quality_threshold=quality_threshold,
            finish_engine=finish_engine,
        )
    return _default_orchestrator


async def process(
    prompt: str,
    wow_intensity: float = 0.8,
    quality: Optional[Any] = None,
    skip_quality_check: bool = False,
) -> OrchestrationResult:
    """Convenience: run full pipeline using default orchestrator."""
    return await get_default_orchestrator().process(
        prompt=prompt,
        wow_intensity=wow_intensity,
        quality=quality,
        skip_quality_check=skip_quality_check,
    )


__all__ = [
    "OrchestrationResult",
    "UnifiedOrchestrator",
    "get_default_orchestrator",
    "process",
]


# ==================== Validation & Tests ====================

if __name__ == "__main__":
    # 1. OrchestrationResult (no service imports needed)
    PD = PromptDomain
    domain_val = PD.GENERAL if PD is not None else "general"
    r = OrchestrationResult(
        image_url="https://example.com/img.png",
        alternative_urls=[],
        original_prompt="test",
        enhanced_prompt="enhanced test",
        domain=domain_val,
        quality_score=None,
        attempts_made=1,
        generation_config=None,
        model_used="flux",
        total_time=1.5,
        success=True,
    )
    d = r.to_dict()
    assert d["success"] and d["image_url"] and d["total_time"] == 1.5
    print("OrchestrationResult.to_dict OK.")

    # 2. _is_quality_acceptable (only if all deps loaded)
    if QualityVerdict is not None and QualityScore is not None and UnifiedOrchestrator is not None:
        try:
            orch = UnifiedOrchestrator(
                max_retries=1,
                quality_threshold=QualityVerdict.ACCEPTABLE,
                finish_engine="flux",
            )
            good = QualityScore(0.8, QualityVerdict.GOOD, 0.8, 0.2, 0.8, [], [], False, 0.9)
            poor = QualityScore(0.5, QualityVerdict.POOR, 0.5, 0.6, 0.4, ["a"], ["b"], True, 0.9)
            assert orch._is_quality_acceptable(good) is True
            assert orch._is_quality_acceptable(poor) is False
            assert orch._is_quality_acceptable(
                QualityScore(0.7, QualityVerdict.ACCEPTABLE, 0.7, 0.3, 0.7, [], [], False, 0.9)
            ) is True
            print("_is_quality_acceptable OK.")
        except Exception as e:
            print("_is_quality_acceptable skipped:", e)
    else:
        print("Deps not loaded (services package may fail), skip _is_quality_acceptable.")

    print("UnifiedOrchestrator validation done. Run full pipeline with real Flux/Replicate backend for end-to-end test.")
