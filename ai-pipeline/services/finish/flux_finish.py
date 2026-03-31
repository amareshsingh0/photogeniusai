"""
Flux image generation finish.

Uses SmartConfigBuilder for steps, guidance, aspect ratio, and scheduler.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, Optional

from services.generation_config import (
    GenerationConfig,
    GenerationQuality,
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


def _record_metric(name: str, **labels: str) -> None:
    try:
        from services.observability import Metrics
        counter = getattr(Metrics, name, None)
        if counter is not None:
            counter.labels(**labels).inc()
    except Exception:
        pass


class FluxFinish:
    """Flux image generation finish."""

    def __init__(self) -> None:
        self.config_builder = SmartConfigBuilder()
        _log().info("FluxFinish initialized with smart config", extra={})

    @trace_function("finish.flux.generate")  # type: ignore[misc]
    async def generate(
        self,
        enhanced_prompt: str,
        negative_prompt: Optional[str] = None,
        domain: Optional[str] = None,
        quality: Optional[GenerationQuality] = None,
        config_override: Optional[GenerationConfig] = None,
        reference_face: Optional[str] = None,
    ) -> FinishResult:
        """
        Generate image with Flux.

        Args:
            enhanced_prompt: Full enhanced prompt
            negative_prompt: Negative prompt
            domain: Prompt domain hint (e.g. "image")
            quality: Quality override
            config_override: Manual config override

        Returns:
            FinishResult with image URL and metadata
        """
        start_time = time.time()

        # Step 1: Build or use config
        if config_override is not None:
            config = config_override
            _log().info("Using manual config override", extra={})
        else:
            config = self.config_builder.auto_build_config(
                prompt=enhanced_prompt,
                domain=domain,
                quality_override=quality,
            )

        # Validate config
        if not self.config_builder.validate_config(config):
            raise ValueError("Invalid generation config")

        _log().info(
            "Generation config",
            extra={
                "steps": config.steps,
                "guidance": config.guidance_scale,
                "scheduler": config.scheduler.value,
                "dimensions": f"{config.width}x{config.height}",
                "quality": config.quality_preset.value,
                "reasoning": config.reasoning,
            },
        )

        # Step 2: Prepare API request
        # Map GenerationQuality enum → SageMaker quality_tier (FAST/STANDARD/PREMIUM)
        _quality_map = {
            "fast":     "FAST",      # UI "Fast"    → 8 steps,  1 cand
            "balanced": "STANDARD",  # UI "Standard"→ 25 steps, 2 cand
            "quality":  "PREMIUM",   # UI "Premium" → 40 steps, 3 cand  (was wrongly STANDARD)
            "ultra":    "PREMIUM",   # UI "Ultra"   → 40 steps, 3 cand  (GPU1 max tier)
        }
        quality_tier = _quality_map.get(config.quality_preset.value, "STANDARD")

        request_data: Dict[str, Any] = {
            "action": "generate_best",   # Required: use Best-of-N pipeline (not legacy)
            "prompt": enhanced_prompt,
            "quality_tier": quality_tier,
            "width": config.width,
            "height": config.height,
        }
        if negative_prompt:
            request_data["negative_prompt"] = negative_prompt
        if config.seed is not None:
            request_data["seed"] = config.seed
        # Pass reference_face to GPU2 post-processor (InstantID, PREMIUM only)
        if reference_face:
            request_data["reference_face"] = reference_face

        # Step 3: Call GPU1 (generate) then GPU2 (post-process for PREMIUM)
        try:
            response = await self._call_flux_api(request_data)

            if not response or "output" not in response:
                raise ValueError("No output from Flux API")

            image_urls = response["output"]
            if not image_urls:
                raise ValueError("Empty output from Flux API")

            primary_url = image_urls[0] if isinstance(image_urls[0], str) else str(image_urls[0])
            urls_list = [u if isinstance(u, str) else str(u) for u in image_urls]
            generation_time = time.time() - start_time

            result = FinishResult(
                image_url=primary_url,
                alternative_urls=urls_list[1:] if len(urls_list) > 1 else [],
                generation_time=generation_time,
                model_used=response.get("model") or "photogenius",
                parameters={
                    "steps": config.steps,
                    "guidance": config.guidance_scale,
                    "scheduler": config.scheduler.value,
                    "dimensions": f"{config.width}x{config.height}",
                    "quality_preset": config.quality_preset.value,
                },
                metadata={
                    "config_reasoning": config.reasoning,
                    "auto_detected": config.auto_detected,
                },
            )

            _log().info(
                "Flux generation complete",
                extra={
                    "time": f"{generation_time:.2f}s",
                    "url_preview": primary_url[:50] if len(primary_url) > 50 else primary_url,
                },
            )

            _record_metric("finish_generations", finish_type="flux", quality=config.quality_preset.value)

            return result

        except Exception as e:
            import traceback
            print(f"[FLUX ERROR] {type(e).__name__}: {e}", flush=True)
            traceback.print_exc()
            logger.error("Flux generation failed: %s: %s", type(e).__name__, e)
            _record_metric("finish_errors", finish_type="flux", error_type=type(e).__name__)
            raise

    async def _call_flux_api(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Call SageMaker ASYNC generation endpoint (GPU 1: photogenius-generation-dev).

        Flow:
          1. Upload request JSON to S3 (async-input/generation/{uuid}.json)
          2. invoke_endpoint_async → returns OutputLocation immediately
          3. Poll S3 output location every 3s until result is written
          4. Parse result and return same dict format as before

        No timeout — async inference runs as long as it needs.
        FAST≈60s, STANDARD≈130s, PREMIUM≈250s (40 steps, full quality).
        """
        import os
        import json as _json
        import uuid
        import asyncio
        from botocore.exceptions import ClientError

        endpoint = (
            os.getenv("GENERATION_ENDPOINT")
            or os.getenv("SAGEMAKER_ENDPOINT")
            or "photogenius-generation-dev"
        )
        region   = os.getenv("AWS_REGION", "us-east-1")
        bucket   = os.getenv("S3_BUCKET", "photogenius-models-dev")

        try:
            import boto3
            from botocore.config import Config as BotocoreConfig
        except ImportError as exc:
            raise RuntimeError("boto3 is required for SageMaker generation") from exc

        s3 = boto3.client("s3", region_name=region)
        runtime = boto3.client(
            "sagemaker-runtime",
            region_name=region,
            config=BotocoreConfig(connect_timeout=10, read_timeout=60),
        )

        # ── Step 1: Upload request JSON to S3 ─────────────────────────────────
        request_id  = str(uuid.uuid4())
        input_key   = f"async-input/generation/{request_id}.json"
        input_s3    = f"s3://{bucket}/{input_key}"

        await asyncio.to_thread(
            s3.put_object,
            Bucket=bucket,
            Key=input_key,
            Body=_json.dumps(request_data).encode("utf-8"),
            ContentType="application/json",
        )
        logger.info("Async input uploaded: %s", input_key)

        # ── Step 2: invoke_endpoint_async (returns immediately) ───────────────
        resp = await asyncio.to_thread(
            runtime.invoke_endpoint_async,
            EndpointName=endpoint,
            InputLocation=input_s3,
            ContentType="application/json",
            InferenceId=request_id,
        )

        output_location = resp["OutputLocation"]  # s3://bucket/async-output/generation/...
        logger.info("Async invoked — output: %s", output_location)

        # Parse output S3 coordinates
        # output_location format: "s3://bucket/key"
        no_prefix   = output_location[len("s3://"):]
        out_bucket  = no_prefix.split("/", 1)[0]
        out_key     = no_prefix.split("/", 1)[1]
        err_key     = out_key + ".error"

        # ── Step 3: Poll S3 until result or error is written ──────────────────
        tier      = request_data.get("quality_tier", "STANDARD")
        rec_model = request_data.get("recommended_model", "")

        # Max poll wait per tier.
        # PREMIUM: 6 candidates×20 steps (~480s) + jury (~30s) + RealVisXL/depth (~180s) + upscale = ~690s warm.
        # Cold-start margin: first request after deploy downloads ~60GB → ~700s init wait.
        # Cold-start ceiling: 700 (init) + 690 (generation) = ~1390s → use 1800s for safety.
        # SAGEMAKER_MODEL_SERVER_TIMEOUT must be >= 1800s (set in deploy script env vars).
        # axios timeout in route.ts must be >= this + network overhead.
        # STANDARD: 1 candidate, 22 steps ≈ 130s → 360s ceiling is safe.
        max_wait  = {"FAST": 180, "STANDARD": 360, "PREMIUM": 1800}.get(tier, 360)
        poll_interval = 3  # seconds between polls
        elapsed       = 0
        result        = None

        logger.info("Polling for result (tier=%s, max_wait=%ds)...", tier, max_wait)

        while elapsed < max_wait:
            await asyncio.sleep(poll_interval)
            elapsed += poll_interval

            # Check success output
            try:
                obj    = await asyncio.to_thread(s3.get_object, Bucket=out_bucket, Key=out_key)
                result = _json.loads(obj["Body"].read())
                logger.info("Async result received after %ds", elapsed)
                break
            except ClientError as e:
                if e.response["Error"]["Code"] != "NoSuchKey":
                    raise  # unexpected S3 error

            # Check error output (SageMaker writes .error on inference failure)
            try:
                err_obj   = await asyncio.to_thread(s3.get_object, Bucket=out_bucket, Key=err_key)
                err_body  = err_obj["Body"].read().decode("utf-8", errors="replace")
                raise RuntimeError(f"Async inference failed: {err_body[:500]}")
            except ClientError as e:
                if e.response["Error"]["Code"] != "NoSuchKey":
                    raise

            if elapsed % 30 == 0:
                logger.info("Still waiting... %ds / %ds (tier=%s)", elapsed, max_wait, tier)

        if result is None:
            raise TimeoutError(
                f"Async inference timed out after {max_wait}s (tier={tier}). "
                "Check CloudWatch logs for MODEL_READY: True before generating."
            )

        # ── Step 4: Parse GPU1 result ──────────────────────────────────────────
        if result.get("status") == "error":
            raise RuntimeError(
                f"SageMaker generation error: {result.get('error', 'unknown')}"
            )

        image_b64 = result.get("image", "")
        if not image_b64:
            raise ValueError(
                f"No image in SageMaker response. Keys: {list(result.keys())}"
            )

        # ── Step 5: GPU2 post-processing for PREMIUM ──────────────────────────
        # GPU1 returns raw jury-winner at 768px draft resolution (no refine/upscale).
        # GPU2 (RealVisXL + ControlNet + InstantID + upscale) renders at target resolution.
        # FAST/STANDARD: GPU1 already applied reality sim + micro-polish inline.
        image_mime = "image/png"  # GPU1 always returns PNG
        if tier == "PREMIUM":
            jury_score = float(result.get("jury_score", 0.5))
            ref_face = request_data.get("reference_face")
            prompt_text = request_data.get("prompt", "")
            # Two-pass: GPU1 returns draft dims + user's target resolution
            target_w = result.get("target_width")   # user-requested width
            target_h = result.get("target_height")  # user-requested height
            processed_b64, gpu2_fmt = await self._call_postprocessor(
                image_b64, prompt_text, jury_score, ref_face, target_w, target_h
            )
            if processed_b64:
                image_b64 = processed_b64
                image_mime = f"image/{gpu2_fmt}" if gpu2_fmt else "image/jpeg"
                logger.info("GPU2 post-processing applied to PREMIUM image")
            else:
                logger.warning("GPU2 post-process fallback — using GPU1 raw image")

        data_url = f"data:{image_mime};base64,{image_b64}"
        return {
            "output": [data_url],
            "model":           result.get("model", ""),
            "generation_time": result.get("generation_time", 0),
            "quality_scores":  result.get("quality_scores", {}),
        }

    async def _call_postprocessor(
        self,
        image_b64: str,
        prompt: str,
        jury_score: float,
        reference_face: Optional[str] = None,
        target_width: Optional[int] = None,
        target_height: Optional[int] = None,
    ):
        """Call GPU2 (photogenius-orchestrator) for PREMIUM post-processing.

        Two-pass architecture:
          - image_b64 is GPU1's 12-step 768px draft (jury winner)
          - GPU2 resizes to target_width×target_height then renders with RealVisXL
          - Output is JPEG (q=92) to stay within SageMaker's 6MB response limit

        Returns: (base64_str, format_str) or (None, None) on failure.
        """
        try:
            import sys
            from pathlib import Path

            # Resolve orchestrator_client import
            _api_root = Path(__file__).resolve().parents[3] / "apps" / "api"
            if _api_root.exists() and str(_api_root) not in sys.path:
                sys.path.insert(0, str(_api_root))

            from app.services.smart.orchestrator_client import orchestrator_client

            result = await orchestrator_client.process_image(
                image_base64=image_b64,
                prompt=prompt,
                quality_tier="PREMIUM",
                jury_score=jury_score,
                reference_face=reference_face,
                target_width=target_width,
                target_height=target_height,
            )

            if result.get("status") == "success":
                b64 = result.get("image_base64") or result.get("image") or None
                fmt = result.get("image_format", "jpeg")
                return b64, fmt
            return None, None

        except Exception as e:
            logger.warning(
                "GPU2 post-processor unavailable (%s: %s) — skipping",
                type(e).__name__, e,
            )
            return None, None
