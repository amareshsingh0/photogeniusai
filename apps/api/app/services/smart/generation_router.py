"""
Generation Router - Routes generation requests to appropriate endpoints based on quality tier

Quality Tiers:
- FAST: SDXL-Turbo (4 steps, ~3-5s)
- STANDARD: SDXL-Base (30 steps, ~25s)
- PREMIUM: SDXL-Base + Refiner (50 steps, ~50s)

Backends:
- Lambda (current)
- SageMaker (future)
- Replicate (fallback)
- Modal (alternative)
"""

import os
import time
import asyncio
from typing import Dict, Optional
import httpx


class GenerationRouter:
    """Routes generation requests to appropriate quality tier endpoints"""

    def __init__(self):
        # Lambda Function URLs (current setup)
        self.lambda_orchestrator_url = os.getenv(
            'LAMBDA_ORCHESTRATOR_URL',
            'https://3gp3xsvqkesxjtf56vdmuxx53a0xaeew.lambda-url.us-east-1.on.aws/'
        )
        self.lambda_generation_url = os.getenv(
            'LAMBDA_GENERATION_URL',
            'https://iq3w5ugxkejdthvjvxavdo7t6a0xhdrs.lambda-url.us-east-1.on.aws/'
        )

        # SageMaker endpoints (future)
        self.sagemaker_fast_endpoint = os.getenv('SAGEMAKER_FAST_ENDPOINT', '')
        self.sagemaker_standard_endpoint = os.getenv('SAGEMAKER_STANDARD_ENDPOINT', '')
        self.sagemaker_premium_endpoint = os.getenv('SAGEMAKER_PREMIUM_ENDPOINT', '')

        # Replicate API (fallback)
        self.replicate_api_token = os.getenv('REPLICATE_API_TOKEN', '')

        self.http_client = httpx.AsyncClient(timeout=120.0)

    async def generate_fast(
        self,
        prompt: str,
        negative_prompt: str = '',
        width: int = 1024,
        height: int = 1024,
        **kwargs
    ) -> Dict:
        """
        Generate with FAST quality tier (SDXL-Turbo, 4 steps, ~3-5s)

        Args:
            prompt: Enhanced prompt
            negative_prompt: Negative prompt
            width: Image width
            height: Image height

        Returns:
            dict: Generation result with image_url and metadata
        """
        start_time = time.time()

        # Try SageMaker first (if configured)
        if self.sagemaker_fast_endpoint:
            result = await self._generate_sagemaker(
                endpoint=self.sagemaker_fast_endpoint,
                prompt=prompt,
                negative_prompt=negative_prompt,
                width=width,
                height=height,
                steps=4,
                guidance_scale=1.0
            )
            if result:
                result['generation_time'] = time.time() - start_time
                result['quality_tier'] = 'FAST'
                result['backend'] = 'SageMaker'
                return result

        # Fallback to Lambda
        result = await self._generate_lambda(
            prompt=prompt,
            negative_prompt=negative_prompt,
            width=width,
            height=height,
            quality_tier='FAST',
            **kwargs
        )

        result['generation_time'] = time.time() - start_time
        result['quality_tier'] = 'FAST'
        result['backend'] = 'Lambda'
        return result

    async def generate_standard(
        self,
        prompt: str,
        negative_prompt: str = '',
        width: int = 1024,
        height: int = 1024,
        mode: str = 'REALISM',
        **kwargs
    ) -> Dict:
        """
        Generate with STANDARD quality tier (SDXL-Base, 30 steps, ~25s)

        Args:
            prompt: Enhanced prompt
            negative_prompt: Negative prompt
            width: Image width
            height: Image height
            mode: Generation mode

        Returns:
            dict: Generation result
        """
        start_time = time.time()

        # Try SageMaker first
        if self.sagemaker_standard_endpoint:
            result = await self._generate_sagemaker(
                endpoint=self.sagemaker_standard_endpoint,
                prompt=prompt,
                negative_prompt=negative_prompt,
                width=width,
                height=height,
                steps=30,
                guidance_scale=7.5
            )
            if result:
                result['generation_time'] = time.time() - start_time
                result['quality_tier'] = 'STANDARD'
                result['backend'] = 'SageMaker'
                return result

        # Fallback to Lambda
        result = await self._generate_lambda(
            prompt=prompt,
            negative_prompt=negative_prompt,
            width=width,
            height=height,
            quality_tier='STANDARD',
            mode=mode,
            **kwargs
        )

        result['generation_time'] = time.time() - start_time
        result['quality_tier'] = 'STANDARD'
        result['backend'] = 'Lambda'
        return result

    async def generate_premium(
        self,
        prompt: str,
        negative_prompt: str = '',
        width: int = 1024,
        height: int = 1024,
        mode: str = 'REALISM',
        **kwargs
    ) -> Dict:
        """
        Generate with PREMIUM quality tier (SDXL-Base + Refiner, 50 steps, ~50s)

        Args:
            prompt: Enhanced prompt
            negative_prompt: Negative prompt
            width: Image width
            height: Image height
            mode: Generation mode

        Returns:
            dict: Generation result
        """
        start_time = time.time()

        # Try SageMaker first
        if self.sagemaker_premium_endpoint:
            result = await self._generate_sagemaker(
                endpoint=self.sagemaker_premium_endpoint,
                prompt=prompt,
                negative_prompt=negative_prompt,
                width=width,
                height=height,
                steps=50,
                guidance_scale=8.5,
                use_refiner=True
            )
            if result:
                result['generation_time'] = time.time() - start_time
                result['quality_tier'] = 'PREMIUM'
                result['backend'] = 'SageMaker'
                return result

        # Fallback to Lambda
        result = await self._generate_lambda(
            prompt=prompt,
            negative_prompt=negative_prompt,
            width=width,
            height=height,
            quality_tier='PREMIUM',
            mode=mode,
            **kwargs
        )

        result['generation_time'] = time.time() - start_time
        result['quality_tier'] = 'PREMIUM'
        result['backend'] = 'Lambda'
        return result

    async def _generate_lambda(
        self,
        prompt: str,
        negative_prompt: str = '',
        width: int = 1024,
        height: int = 1024,
        quality_tier: str = 'STANDARD',
        mode: str = 'REALISM',
        **kwargs
    ) -> Dict:
        """
        Generate using Lambda orchestrator

        Args:
            prompt: Enhanced prompt
            negative_prompt: Negative prompt
            width: Image width
            height: Image height
            quality_tier: Quality tier
            mode: Generation mode

        Returns:
            dict: Generation result
        """
        try:
            payload = {
                'body': {
                    'prompt': prompt,
                    'negative_prompt': negative_prompt,
                    'width': width,
                    'height': height,
                    'quality_tier': quality_tier,
                    'mode': mode,
                    **kwargs
                }
            }

            response = await self.http_client.post(
                self.lambda_orchestrator_url,
                json=payload
            )

            response.raise_for_status()
            data = response.json()

            return {
                'image_url': data.get('image_url') or data.get('images', {}).get('final'),
                'preview_url': data.get('preview_url') or data.get('images', {}).get('preview'),
                'metadata': data.get('metadata', {}),
                'success': True
            }

        except Exception as e:
            print(f"Lambda generation error: {e}")
            return {
                'image_url': None,
                'error': str(e),
                'success': False
            }

    async def _generate_sagemaker(
        self,
        endpoint: str,
        prompt: str,
        negative_prompt: str = '',
        width: int = 1024,
        height: int = 1024,
        steps: int = 30,
        guidance_scale: float = 7.5,
        use_refiner: bool = False
    ) -> Optional[Dict]:
        """
        Generate using SageMaker endpoint

        Args:
            endpoint: SageMaker endpoint name
            prompt: Enhanced prompt
            negative_prompt: Negative prompt
            width: Image width
            height: Image height
            steps: Number of steps
            guidance_scale: Guidance scale
            use_refiner: Use refiner

        Returns:
            dict or None: Generation result or None if failed
        """
        try:
            import boto3
            import json as json_lib

            runtime = boto3.client('sagemaker-runtime')

            payload = {
                'prompt': prompt,
                'negative_prompt': negative_prompt,
                'width': width,
                'height': height,
                'num_inference_steps': steps,
                'guidance_scale': guidance_scale,
                'use_refiner': use_refiner
            }

            response = runtime.invoke_endpoint(
                EndpointName=endpoint,
                ContentType='application/json',
                Body=json_lib.dumps(payload)
            )

            result = json_lib.loads(response['Body'].read())

            return {
                'image_url': result.get('image_url'),
                'preview_url': result.get('preview_url'),
                'metadata': result.get('metadata', {}),
                'success': True
            }

        except Exception as e:
            print(f"SageMaker generation error: {e}")
            return None

    async def _generate_huggingface(
        self,
        prompt: str,
        negative_prompt: str = '',
        width: int = 1024,
        height: int = 1024,
        steps: int = 30,
        guidance_scale: float = 7.5,
        model: str = 'stabilityai/stable-diffusion-xl-base-1.0'
    ) -> Optional[Dict]:
        """
        Generate using HuggingFace Inference API

        Args:
            prompt: Enhanced prompt
            negative_prompt: Negative prompt
            width: Image width
            height: Image height
            steps: Number of steps
            guidance_scale: Guidance scale
            model: Model ID on HuggingFace

        Returns:
            dict or None: Generation result or None if failed
        """
        import os
        import base64
        from io import BytesIO

        try:
            api_token = os.getenv('HUGGINGFACE_API_TOKEN')
            if not api_token:
                print("HuggingFace API token not found")
                return None

            # HuggingFace Inference API endpoint
            api_url = f"https://api-inference.huggingface.co/models/{model}"

            headers = {
                "Authorization": f"Bearer {api_token}",
                "Content-Type": "application/json"
            }

            payload = {
                "inputs": prompt,
                "parameters": {
                    "negative_prompt": negative_prompt,
                    "width": width,
                    "height": height,
                    "num_inference_steps": steps,
                    "guidance_scale": guidance_scale
                }
            }

            response = await self.http_client.post(
                api_url,
                headers=headers,
                json=payload,
                timeout=120.0
            )

            if response.status_code == 503:
                # Model is loading, wait and retry
                print("Model loading, waiting 20s...")
                await asyncio.sleep(20)
                response = await self.http_client.post(
                    api_url,
                    headers=headers,
                    json=payload,
                    timeout=120.0
                )

            response.raise_for_status()

            # HuggingFace returns image bytes
            image_bytes = response.content

            # Convert to base64
            image_base64 = base64.b64encode(image_bytes).decode('utf-8')
            image_url = f"data:image/png;base64,{image_base64}"

            return {
                'image_url': image_url,
                'preview_url': None,
                'metadata': {
                    'model': model,
                    'steps': steps,
                    'guidance_scale': guidance_scale
                },
                'success': True
            }

        except Exception as e:
            print(f"HuggingFace generation error: {e}")
            return None

    async def _generate_replicate(
        self,
        prompt: str,
        negative_prompt: str = '',
        width: int = 1024,
        height: int = 1024,
        steps: int = 30,
        guidance_scale: float = 7.5,
        model: str = 'stability-ai/sdxl:39ed52f2a78e934b3ba6e2a89f5b1c712de7dfea535525255b1aa35c5565e08b'
    ) -> Optional[Dict]:
        """
        Generate using Replicate API

        Args:
            prompt: Enhanced prompt
            negative_prompt: Negative prompt
            width: Image width
            height: Image height
            steps: Number of steps
            guidance_scale: Guidance scale
            model: Replicate model version

        Returns:
            dict or None: Generation result or None if failed
        """
        import os
        import asyncio

        try:
            api_token = os.getenv('REPLICATE_API_TOKEN')
            if not api_token:
                print("Replicate API token not found")
                return None

            headers = {
                "Authorization": f"Token {api_token}",
                "Content-Type": "application/json"
            }

            # Create prediction
            payload = {
                "version": model.split(':')[1] if ':' in model else model,
                "input": {
                    "prompt": prompt,
                    "negative_prompt": negative_prompt,
                    "width": width,
                    "height": height,
                    "num_inference_steps": steps,
                    "guidance_scale": guidance_scale
                }
            }

            response = await self.http_client.post(
                "https://api.replicate.com/v1/predictions",
                headers=headers,
                json=payload
            )

            response.raise_for_status()
            prediction = response.json()

            # Poll for completion
            prediction_url = prediction['urls']['get']
            max_attempts = 60  # 60 attempts = ~2 minutes max wait

            for attempt in range(max_attempts):
                await asyncio.sleep(2)  # Wait 2 seconds between polls

                status_response = await self.http_client.get(
                    prediction_url,
                    headers=headers
                )
                status_response.raise_for_status()
                status_data = status_response.json()

                if status_data['status'] == 'succeeded':
                    output = status_data.get('output')
                    if isinstance(output, list) and len(output) > 0:
                        image_url = output[0]
                    else:
                        image_url = output

                    return {
                        'image_url': image_url,
                        'preview_url': None,
                        'metadata': {
                            'model': model,
                            'steps': steps,
                            'guidance_scale': guidance_scale,
                            'prediction_id': prediction['id']
                        },
                        'success': True
                    }

                elif status_data['status'] == 'failed':
                    print(f"Replicate generation failed: {status_data.get('error')}")
                    return None

            print("Replicate generation timed out")
            return None

        except Exception as e:
            print(f"Replicate generation error: {e}")
            return None

    async def close(self):
        """Close HTTP client"""
        await self.http_client.aclose()


# Singleton instance
generation_router = GenerationRouter()


# ══════════════════════════════════════════════════════════════════════════════
# SmartGenerationRouter — API-first routing (fast-move phase, Mar 2026)
# ══════════════════════════════════════════════════════════════════════════════
#
# Wraps fal.ai + Ideogram (external APIs) with the same response contract as
# GenerationRouter above. Falls back to existing GenerationRouter on error.
#
# Pipeline:
#   1. detect_capability_bucket(prompt) → bucket
#   2. ClaudePromptEngine.enhance()     → enhanced prompt + negative
#   3. get_model_config(bucket, tier)   → which API + model
#   4. fal_client / ideogram_client     → generate (ensemble if premium/ultra)
#   5. Return best image (or all if num_images > 1)
# ══════════════════════════════════════════════════════════════════════════════

class SmartGenerationRouter:
    """
    API-first generation router.

    Feature flags (env):
      USE_IDEOGRAM=false   → typography bucket falls back to fal.ai flux_pro
      USE_ANTHROPIC=false  → Claude disabled, Gemini used instead
      USE_GEMINI_ENGINE=true → Gemini 2.0 Flash for prompt engine

    Usage:
        result = await smart_router.generate(
            prompt="a luxury car ad at golden hour",
            tier="standard",
            style="Realistic",
            creative_type="ad",
            width=1024,
            height=1024,
        )
    """

    # Read flags once at class level (runtime env, no restart needed if using dotenv)
    _USE_IDEOGRAM: bool = os.getenv("USE_IDEOGRAM", "false").lower() == "true"
    _USE_ANTHROPIC: bool = os.getenv("USE_ANTHROPIC", "false").lower() == "true"

    def _get_prompt_engine(self):
        """Return the active prompt engine based on feature flags."""
        if self._USE_ANTHROPIC:
            from app.services.smart.claude_prompt_engine import claude_prompt_engine
            return claude_prompt_engine
        # Default: Gemini (falls back to heuristic if key not set)
        from app.services.smart.gemini_prompt_engine import gemini_prompt_engine
        return gemini_prompt_engine

    async def generate(
        self,
        prompt: str,
        tier: str = "standard",
        style: str = "photo",
        creative_type: str = "photo",
        width: int = 1024,
        height: int = 1024,
        reference_image_url: Optional[str] = None,
        extra_context: Optional[str] = None,
        user_preferences: Optional[Dict] = None,
    ) -> Dict:
        """
        Full smart generation: bucket detect → prompt enhance → API generate.

        Returns standard contract:
          {
            "image_url": str,
            "all_urls": List[str],
            "enhanced_prompt": str,
            "original_prompt": str,
            "capability_bucket": str,
            "model_used": str,
            "backend": str,
            "generation_time": float,
            "prompt_engine": "gemini" | "claude" | "heuristic",
            "creative_brief": dict,
            "success": bool,
            "quality_tier": str,
            "flags": dict,
          }
        """
        from app.services.smart.config import detect_capability_bucket, get_model_config
        from app.services.smart.ensemble import run_ensemble, _cache_key, _cache_get, _cache_set

        start = time.time()

        # ── 1. Detect capability bucket ────────────────────────────────────────
        bucket = detect_capability_bucket(prompt)

        # ── 1b. Style DNA bias — boost preferred bucket if user has history ────
        dna = (user_preferences or {}).get("style_dna", {})
        if dna:
            bucket_scores: Dict = dna.get("buckets", {})
            # If the detected bucket has a negative score and user has a strong
            # alternative preference, switch to the preferred bucket
            detected_score = bucket_scores.get(bucket, 0)
            if detected_score < -2:
                # User dislikes this bucket — pick their most liked alternative
                best = max(
                    ((b, s) for b, s in bucket_scores.items() if b != bucket and s > 0),
                    key=lambda x: x[1],
                    default=(None, 0),
                )
                if best[0]:
                    print(f"[SmartRouter] DNA bias: {bucket} (score={detected_score}) → {best[0]} (score={best[1]})")
                    bucket = best[0]

            # Preferred style hint → append to extra_context for prompt engine
            style_scores: Dict = dna.get("styles", {})
            if style_scores:
                top_style = max(style_scores, key=lambda s: style_scores[s], default=None)
                if top_style and style_scores.get(top_style, 0) >= 3:
                    dna_hint = f"User prefers {top_style} style."
                    extra_context = f"{extra_context} {dna_hint}".strip() if extra_context else dna_hint

        model_cfg = get_model_config(bucket, tier)
        model_key = model_cfg.get("model", "flux_2_pro")
        rendering_speed = model_cfg.get("rendering_speed", "BALANCED")

        # ── 2. Prompt engine — check cache first ───────────────────────────────
        prompt_engine = self._get_prompt_engine()
        ck = _cache_key(prompt, tier, bucket)
        cached_enhanced = _cache_get(ck)

        if cached_enhanced:
            enhanced = cached_enhanced
            print(f"[SmartRouter] prompt cache HIT bucket={bucket} tier={tier}")
        else:
            model_display = {
                "flux_2_pro":       "Flux 2 Pro",
                "flux_2_dev":       "Flux 2 Dev",
                "flux_2_max":       "Flux 2 Max",
                "flux_2_turbo":     "Flux 2 Turbo",
                "flux_schnell":     "Flux Schnell",
                "flux_kontext":     "Flux Kontext Pro",
                "flux_kontext_max": "Flux Kontext Max",
                "ideogram_turbo":   "Ideogram V3 Turbo",
                "ideogram_quality": "Ideogram V3 Quality",
                "recraft_v4":       "Recraft V4",
                "recraft_v4_svg":   "Recraft V4 SVG",
                "hunyuan_image":    "Hunyuan Image",
            }.get(model_key, model_key)

            enhanced = prompt_engine.enhance(
                raw_prompt=prompt,
                model_name=model_display,
                capability_bucket=bucket,
                creative_type=creative_type,
                style=style,
                extra_context=extra_context,
                tier=tier,
            )
            _cache_set(ck, enhanced)

        final_prompt = enhanced["prompt"]
        negative_prompt = enhanced["negative_prompt"]

        # ── 3. Image size ──────────────────────────────────────────────────────
        if width > height:
            img_size = "landscape_16_9"
        elif height > width:
            img_size = "portrait_9_16"
        else:
            img_size = "square_hd"

        # ── 4. Ensemble generation (tier-aware) ────────────────────────────────
        # FAST:     1× Schnell (~₹0.10)
        # STANDARD: 3× Schnell → jury → ESRGAN (~₹0.47)
        # PREMIUM:  3× Schnell → jury → Flux 2 Dev refine (~₹1.14)
        # ULTRA:    2× Flux 2 Pro → jury (~₹4.20)
        result: Dict = {}
        try:
            result = await run_ensemble(
                tier=tier,
                bucket=bucket,
                prompt=final_prompt,
                negative_prompt=negative_prompt,
                image_size=img_size,
                reference_image_url=reference_image_url,
                rendering_speed=rendering_speed,
            )
        except Exception as e:
            print(f"[SmartRouter] ensemble error: {e}")
            result = {"success": False, "metadata": {"error": str(e)}}

        # ── 5. Log result ──────────────────────────────────────────────────────
        if not result.get("success"):
            print(f"[SmartRouter] ensemble failed: {result.get('metadata', {}).get('error', 'unknown')}")
        else:
            print(f"[SmartRouter] OK strategy={result.get('ensemble_strategy')} "
                  f"time={result.get('ensemble_time', 0):.1f}s "
                  f"jury={result.get('jury_score', 'n/a')} "
                  f"upscaled={result.get('upscaled', False)}")

        # ── 6. Build unified response ──────────────────────────────────────────
        return {
            "image_url":          result.get("image_url"),
            "all_urls":           result.get("all_urls", []),
            "enhanced_prompt":    final_prompt,
            "original_prompt":    prompt,
            "capability_bucket":  bucket,
            "model_used":         result.get("model", model_key),
            "backend":            result.get("backend", "multi_provider"),
            "provider":           result.get("provider", "unknown"),
            "cost_usd":           result.get("cost_usd", 0.0),
            "cost_inr":           result.get("cost_inr", 0.0),
            "generation_time":    time.time() - start,
            "ensemble_strategy":  result.get("ensemble_strategy", "single"),
            "jury_score":         result.get("jury_score"),
            "upscaled":           result.get("upscaled", False),
            "candidates_count":   result.get("candidates_count", 1),
            "prompt_cache_hit":   cached_enhanced is not None,
            "prompt_engine":      enhanced.get("engine", "heuristic"),
            "creative_brief":     enhanced.get("brief", {}),
            "success":            result.get("success", False),
            "quality_tier":       tier.upper(),
            "negative_prompt":    negative_prompt,
            "flags": {
                "use_ideogram":   self._USE_IDEOGRAM,
                "use_anthropic":  self._USE_ANTHROPIC,
            },
        }


# Smart singleton
smart_router = SmartGenerationRouter()
