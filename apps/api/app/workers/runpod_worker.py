"""
RunPod GPU Worker Integration

Alternative to Modal.com for GPU compute with dedicated GPU instances.
Supports both serverless and dedicated GPU endpoints.
"""

import logging
from typing import Dict, List, Optional, Any
import httpx
import asyncio
from urllib.parse import urlparse

from app.core.config import get_settings

logger = logging.getLogger(__name__)


class RunPodWorkerClient:
    """
    Client for RunPod GPU workers
    
    Supports both serverless endpoints and dedicated GPU pods.
    """
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize RunPod client
        
        Args:
            api_key: RunPod API key (if None, reads from settings)
        """
        self.settings = get_settings()
        self.api_key = api_key or getattr(self.settings, "RUNPOD_API_KEY", None)
        self.base_url = "https://api.runpod.io/v2"
        
        # Endpoint IDs (configure these in settings or environment)
        self.generation_endpoint = getattr(
            self.settings, "RUNPOD_GENERATION_ENDPOINT", None
        )
        self.training_endpoint = getattr(
            self.settings, "RUNPOD_TRAINING_ENDPOINT", None
        )
        
        if not self.api_key:
            logger.warning("RunPod API key not configured. Set RUNPOD_API_KEY")
            self.available = False
        else:
            self.available = True
    
    async def generate(
        self,
        prompt: str,
        negative_prompt: str,
        identity_data: Dict,
        mode: str,
        config: Dict,
        user_id: str,
        generation_id: str,
    ) -> Dict:
        """
        Submit generation job to RunPod
        
        Args:
            prompt: Generation prompt
            negative_prompt: Negative prompt
            identity_data: Identity/LoRA data
            mode: Generation mode
            config: Generation configuration
            user_id: User ID
            generation_id: Generation job ID
            
        Returns:
            Result dictionary with success status and image URLs
        """
        if not self.available:
            return {
                "success": False,
                "error": "RunPod not configured",
            }
        
        if not self.generation_endpoint:
            return {
                "success": False,
                "error": "RunPod generation endpoint not configured",
            }
        
        try:
            # Prepare payload
            payload = {
                "input": {
                    "prompt": prompt,
                    "negative_prompt": negative_prompt,
                    "identity_data": identity_data,
                    "mode": mode,
                    "config": config,
                    "user_id": user_id,
                    "generation_id": generation_id,
                }
            }
            
            # Submit job
            async with httpx.AsyncClient(timeout=600.0) as client:
                response = await client.post(
                    f"{self.base_url}/{self.generation_endpoint}/run",
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    json=payload,
                )
                response.raise_for_status()
                
                result = response.json()
                job_id = result.get("id")
            
            if not job_id:
                return {
                    "success": False,
                    "error": "Failed to get job ID from RunPod",
                }
            
            logger.info(f"RunPod generation job {job_id} submitted")
            
            # Poll for completion
            max_polls = 300  # 10 minutes max (2s * 300)
            poll_count = 0
            
            while poll_count < max_polls:
                await asyncio.sleep(2)  # Poll every 2 seconds
                poll_count += 1
                
                async with httpx.AsyncClient(timeout=30.0) as client:
                    response = await client.get(
                        f"{self.base_url}/{self.generation_endpoint}/status/{job_id}",
                        headers={"Authorization": f"Bearer {self.api_key}"},
                    )
                    response.raise_for_status()
                    
                    status = response.json()
                    job_status = status.get("status")
                
                if job_status == "COMPLETED":
                    output = status.get("output", {})
                    logger.info(f"RunPod generation job {job_id} completed")
                    return {
                        "success": True,
                        **output,
                        "metadata": {
                            "provider": "runpod",
                            "job_id": job_id,
                        }
                    }
                
                elif job_status == "FAILED":
                    error = status.get("error", "Unknown error")
                    logger.error(f"RunPod generation job {job_id} failed: {error}")
                    return {
                        "success": False,
                        "error": error,
                        "metadata": {
                            "provider": "runpod",
                            "job_id": job_id,
                        }
                    }
                
                # Log progress for long-running jobs
                if poll_count % 30 == 0:  # Every minute
                    logger.info(f"RunPod generation job {job_id} still running...")
            
            # Timeout
            return {
                "success": False,
                "error": "RunPod generation job timed out",
                "metadata": {
                    "provider": "runpod",
                    "job_id": job_id,
                }
            }
                
        except httpx.HTTPStatusError as e:
            logger.error(f"RunPod HTTP error: {e.response.status_code} - {e.response.text}")
            return {
                "success": False,
                "error": f"RunPod HTTP error: {e.response.status_code}",
            }
        except Exception as e:
            logger.error(f"RunPod generation failed: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e),
            }
    
    async def train(
        self,
        user_id: str,
        identity_id: str,
        photo_urls: List[str],
        config: Dict,
    ) -> Dict:
        """
        Submit training job to RunPod
        
        Args:
            user_id: User ID
            identity_id: Identity ID
            photo_urls: List of photo S3 URLs
            config: Training configuration
            
        Returns:
            Result dictionary with success status and LoRA path
        """
        if not self.available:
            return {
                "success": False,
                "error": "RunPod not configured",
            }
        
        if not self.training_endpoint:
            return {
                "success": False,
                "error": "RunPod training endpoint not configured",
            }
        
        try:
            payload = {
                "input": {
                    "user_id": user_id,
                    "identity_id": identity_id,
                    "photo_urls": photo_urls,
                    "config": config,
                }
            }
            
            async with httpx.AsyncClient(timeout=1800.0) as client:
                response = await client.post(
                    f"{self.base_url}/{self.training_endpoint}/run",
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    json=payload,
                )
                response.raise_for_status()
                
                result = response.json()
                job_id = result.get("id")
            
            if not job_id:
                return {
                    "success": False,
                    "error": "Failed to get job ID from RunPod",
                }
            
            logger.info(f"RunPod training job {job_id} submitted")
            
            # Poll for completion (longer timeout for training)
            max_polls = 1800  # 60 minutes max (2s * 1800)
            poll_count = 0
            
            while poll_count < max_polls:
                await asyncio.sleep(5)  # Poll every 5 seconds for training
                poll_count += 1
                
                async with httpx.AsyncClient(timeout=30.0) as client:
                    response = await client.get(
                        f"{self.base_url}/{self.training_endpoint}/status/{job_id}",
                        headers={"Authorization": f"Bearer {self.api_key}"},
                    )
                    response.raise_for_status()
                    
                    status = response.json()
                    job_status = status.get("status")
                
                if job_status == "COMPLETED":
                    output = status.get("output", {})
                    logger.info(f"RunPod training job {job_id} completed")
                    return {
                        "success": True,
                        **output,
                        "metadata": {
                            "provider": "runpod",
                            "job_id": job_id,
                        }
                    }
                
                elif job_status == "FAILED":
                    error = status.get("error", "Unknown error")
                    logger.error(f"RunPod training job {job_id} failed: {error}")
                    return {
                        "success": False,
                        "error": error,
                        "metadata": {
                            "provider": "runpod",
                            "job_id": job_id,
                        }
                    }
                
                # Log progress for long-running jobs
                if poll_count % 60 == 0:  # Every 5 minutes
                    logger.info(f"RunPod training job {job_id} still running...")
            
            # Timeout
            return {
                "success": False,
                "error": "RunPod training job timed out",
                "metadata": {
                    "provider": "runpod",
                    "job_id": job_id,
                }
            }
                
        except httpx.HTTPStatusError as e:
            logger.error(f"RunPod HTTP error: {e.response.status_code} - {e.response.text}")
            return {
                "success": False,
                "error": f"RunPod HTTP error: {e.response.status_code}",
            }
        except Exception as e:
            logger.error(f"RunPod training failed: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e),
            }
    
    async def health_check(self) -> bool:
        """
        Check if RunPod is accessible
        
        Returns:
            True if RunPod API is accessible
        """
        if not self.available:
            return False
        
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                # Try to list endpoints (requires API key)
                response = await client.get(
                    f"{self.base_url}/endpoints",
                    headers={"Authorization": f"Bearer {self.api_key}"},
                )
                return response.status_code == 200
        except Exception as e:
            logger.error(f"RunPod health check failed: {e}")
            return False
    
    def get_statistics(self) -> Dict:
        """Get RunPod worker statistics"""
        return {
            "available": self.available,
            "provider": "runpod",
            "generation_endpoint": self.generation_endpoint is not None,
            "training_endpoint": self.training_endpoint is not None,
        }
