"""
Orchestrator Client - Calls the Post-Processing GPU (GPU 2) endpoint.

GPU 2 runs RealVisXL + ControlNet + InstantID for PREMIUM post-processing.

Actions:
- post_process: RealVisXL refine + upscale + InstantID (if reference_face)
- health: Health check

Backend: SageMaker (photogenius-orchestrator)
"""

import os
import time
import json
import logging
from typing import Dict, Optional


logger = logging.getLogger(__name__)


class OrchestratorClient:
    """Client for the AI Director GPU endpoint (Mixtral-8x7B GPTQ only)."""

    def __init__(self):
        self.endpoint_name = os.getenv('ORCHESTRATOR_ENDPOINT', 'photogenius-orchestrator')
        self.aws_region = os.getenv('AWS_REGION', 'us-east-1')
        self._runtime = None

    @property
    def runtime(self):
        if self._runtime is None:
            import boto3
            from botocore.config import Config
            config = Config(
                read_timeout=300,   # GPU2 RealVisXL refine takes ~90s warm
                connect_timeout=10,
                retries={'max_attempts': 1},
            )
            self._runtime = boto3.client(
                'sagemaker-runtime',
                region_name=self.aws_region,
                config=config,
            )
        return self._runtime

    def _invoke(self, payload: Dict) -> Dict:
        """Invoke orchestrator endpoint. Auto-retries once on stale SSL connections."""
        body = json.dumps(payload)
        for attempt in range(2):
            try:
                response = self.runtime.invoke_endpoint(
                    EndpointName=self.endpoint_name,
                    ContentType='application/json',
                    Body=body,
                )
                raw = json.loads(response['Body'].read())
                # HF container 2.6.0 may serialize output_fn's tuple (json_str, content_type)
                # as a JSON array ["...", "application/json"]. Unwrap it defensively.
                if isinstance(raw, list):
                    if raw and isinstance(raw[0], str):
                        try:
                            raw = json.loads(raw[0])
                        except Exception:
                            raw = {}
                    elif raw and isinstance(raw[0], dict):
                        raw = raw[0]
                    else:
                        raw = {}
                return raw
            except Exception as e:
                err_name = type(e).__name__
                if attempt == 0 and ('SSL' in err_name or 'ConnectionClosed' in err_name
                                      or 'EndpointConnection' in err_name):
                    logger.warning("[ORCHESTRATOR] %s on attempt 1, resetting client and retrying", err_name)
                    self._runtime = None  # Force fresh connection
                    continue
                raise


    async def process_image(
        self,
        image_base64: str,
        prompt: str,
        quality_tier: str = "PREMIUM",
        jury_score: float = 0.5,
        reference_face: Optional[str] = None,
        target_width: Optional[int] = None,
        target_height: Optional[int] = None,
    ) -> Dict:
        """Post-process PREMIUM image on GPU2: RealVisXL refine + upscale + InstantID.

        Two-pass: image_base64 is a 768px draft; target_width/target_height tells GPU2
        what resolution to render at before upscaling.

        GPU2 pipeline:
          0. Resize 768px draft → target_width×target_height (LANCZOS)
          1. [if reference_face] InsightFace extract embedding → InstantID condition
          2. RealVisXL img2img true render (strength 0.45–0.65, 35 steps)
          3. ControlNet depth + OpenPose conditioning
          4. RealESRGAN 2x upscale
          5. Reality simulation + micro-polish

        Returns:
            {
                "status": "success",
                "image_base64": "...",   (rendered + upscaled)
                "process_time": 87.3,
                "used_instantid": false
            }
        Fallback: returns original image_base64 unchanged on any failure.
        """
        import asyncio
        start = time.time()
        try:
            payload = {
                'action': 'post_process',
                'image': image_base64,
                'prompt': prompt,
                'quality_tier': quality_tier,
                'jury_score': jury_score,
            }
            if reference_face:
                payload['reference_face'] = reference_face
            if target_width:
                payload['target_width'] = target_width
            if target_height:
                payload['target_height'] = target_height

            result = await asyncio.to_thread(self._invoke, payload)

            if result.get('status') == 'success':
                logger.info(
                    f"[ORCHESTRATOR] Post-process OK in {time.time()-start:.1f}s "
                    f"(instantid={result.get('used_instantid', False)}, "
                    f"size={result.get('output_size', '?')})"
                )
                return result
            else:
                logger.warning(
                    f"[ORCHESTRATOR] post_process error: {result.get('error')} "
                    f"— returning original image"
                )
                return {'status': 'fallback', 'image_base64': image_base64}

        except Exception as e:
            logger.warning(
                f"[ORCHESTRATOR] post_process failed ({type(e).__name__}: {e}) "
                f"— returning original image"
            )
            return {'status': 'fallback', 'image_base64': image_base64}

    async def health(self) -> Dict:
        """Check GPU2 post-processor health."""
        try:
            return self._invoke({'action': 'health'})
        except Exception as e:
            return {'status': 'unavailable', 'error': str(e)}

    async def close(self):
        pass


# Singleton
orchestrator_client = OrchestratorClient()
