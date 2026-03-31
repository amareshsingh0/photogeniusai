"""
Replicate (SDXL/Flux) image generation finish.

Uses SmartConfigBuilder and maps scheduler to Replicate format.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional, Union

from services.generation_config import (
    GenerationConfig,
    GenerationQuality,
    Scheduler,
    SmartConfigBuilder,
)

from .types import FinishResult

logger = logging.getLogger(__name__)

# Optional observability
try:
    from services.observability import StructuredLogger, trace_function
except Exception:
    trace_function = lambda n=None: (lambda f: f)  # type: ignore[assignment, misc]
    StructuredLogger = None


def _log():
    logger_cls = StructuredLogger
    if logger_cls is not None:
        return logger_cls(__name__)
    return logger


# Map our Scheduler enum to Replicate API names
REPLICATE_SCHEDULER_MAP = {
    Scheduler.EULER_A: "K_EULER_ANCESTRAL",
    Scheduler.DPM_2M_KARRAS: "DPMSolverMultistep",
    Scheduler.DDIM: "DDIM",
    Scheduler.PNDM: "PNDM",
    Scheduler.UNIPC: "UniPC",
}


class ReplicateFinish:
    """Replicate (SDXL/Flux) finish."""

    def __init__(self, model: str = "flux-1.1-pro") -> None:
        self.config_builder = SmartConfigBuilder()
        self.model = model
        _log().info("ReplicateFinish initialized", extra={"model": model})

    @trace_function("finish.replicate.generate")  # type: ignore[misc]
    async def generate(
        self,
        enhanced_prompt: str,
        negative_prompt: Optional[str] = None,
        domain: Optional[str] = None,
        quality: Optional[GenerationQuality] = None,
        config_override: Optional[GenerationConfig] = None,
    ) -> FinishResult:
        """Generate with Replicate API."""
        start_time = time.time()

        # Build config
        if config_override is not None:
            config = config_override
        else:
            config = self.config_builder.auto_build_config(
                prompt=enhanced_prompt,
                domain=domain,
                quality_override=quality,
            )

        # Validate
        if not self.config_builder.validate_config(config):
            raise ValueError("Invalid config")

        _log().info(
            "Replicate config",
            extra={
                "model": self.model,
                "steps": config.steps,
                "guidance": config.guidance_scale,
                "dimensions": f"{config.width}x{config.height}",
                "reasoning": config.reasoning,
            },
        )

        replicate_scheduler = REPLICATE_SCHEDULER_MAP.get(
            config.scheduler,
            "K_EULER_ANCESTRAL",
        )

        replicate_input: Dict[str, Any] = {
            "prompt": enhanced_prompt,
            "width": config.width,
            "height": config.height,
            "num_inference_steps": config.steps,
            "guidance_scale": config.guidance_scale,
            "scheduler": replicate_scheduler,
            "num_outputs": config.num_images,
        }
        if negative_prompt:
            replicate_input["negative_prompt"] = negative_prompt
        if config.seed is not None:
            replicate_input["seed"] = config.seed

        # Call API
        try:
            output = await self._run_replicate(replicate_input)

            if output is None:
                raise ValueError("No output from Replicate")

            # Handle output (URL or list of URLs)
            if isinstance(output, list):
                image_urls = [o if isinstance(o, str) else str(o) for o in output]
            else:
                image_urls = [output if isinstance(output, str) else str(output)]

            if not image_urls:
                raise ValueError("Empty output from Replicate")

            generation_time = time.time() - start_time

            result = FinishResult(
                image_url=image_urls[0],
                alternative_urls=image_urls[1:],
                generation_time=generation_time,
                model_used=self.model,
                parameters={
                    "steps": config.steps,
                    "guidance": config.guidance_scale,
                    "scheduler": config.scheduler.value,
                    "dimensions": f"{config.width}x{config.height}",
                },
                metadata={
                    "config_reasoning": config.reasoning,
                    "auto_detected": config.auto_detected,
                },
            )

            _log().info(
                "Replicate generation complete",
                extra={"time": f"{generation_time:.2f}s", "model": self.model},
            )

            return result

        except Exception as e:
            _log().error(
                "Replicate generation failed",
                extra={"error": str(e), "error_type": type(e).__name__},
            )
            raise

    async def _run_replicate(self, input_data: Dict[str, Any]) -> Union[str, List[str], None]:
        """
        Run Replicate prediction. Override in subclasses for real integration.

        Returns:
            Single image URL, list of image URLs, or None on failure.
        """
        # Stub: real implementation would use replicate.run(...)
        raise NotImplementedError(
            "Replicate API not configured. Implement _run_replicate or set Replicate token."
        )
