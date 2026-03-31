"""
Worker Manager

Manages GPU workers with automatic failover, health checks, and load balancing.
Primary: AWS (SageMaker/Lambda). Modal and RunPod are legacy/optional.
"""

import logging
from typing import Dict, List, Optional, Literal
from enum import Enum
import asyncio
from datetime import datetime, timedelta

from app.core.config import get_settings
from .modal_worker import ModalWorkerClient
from .runpod_worker import RunPodWorkerClient
from .metrics import (
    get_metrics_collector,
    JobType,
    ProviderType,
)
from app.services.websocket.manager import get_websocket_manager

logger = logging.getLogger(__name__)


class WorkerProvider(Enum):
    """GPU worker providers (AWS primary, Modal/RunPod legacy)."""
    AWS = "aws"
    MODAL = "modal"
    RUNPOD = "runpod"


class WorkerManager:
    """
    Manages GPU workers with failover and load balancing
    
    Features:
    - Automatic failover between providers
    - Health checking and monitoring
    - Statistics tracking
    - Cost optimization
    - Performance monitoring
    """
    
    def __init__(
        self,
        primary_provider: Optional[WorkerProvider] = None,
        fallback_provider: Optional[WorkerProvider] = None,
        runpod_api_key: Optional[str] = None,
    ):
        """
        Initialize worker manager
        
        Args:
            primary_provider: Primary GPU provider (default: AWS)
            fallback_provider: Fallback if primary fails (optional)
            runpod_api_key: RunPod API key (if using RunPod)
        """
        self.settings = get_settings()
        
        # Determine providers from settings or defaults (AWS primary)
        if primary_provider is None:
            provider_str = getattr(self.settings, "GPU_WORKER_PRIMARY", "aws").lower()
            if provider_str == "aws":
                primary_provider = WorkerProvider.AWS
            elif provider_str == "modal":
                primary_provider = WorkerProvider.MODAL
            else:
                primary_provider = WorkerProvider.RUNPOD
        
        if fallback_provider is None:
            if primary_provider == WorkerProvider.AWS:
                fallback_provider = None  # AWS only, no fallback
            elif primary_provider == WorkerProvider.MODAL:
                fallback_provider = WorkerProvider.RUNPOD
            else:
                fallback_provider = WorkerProvider.MODAL
        
        self.primary_provider = primary_provider
        self.fallback_provider = fallback_provider
        
        # Initialize clients (Modal/RunPod only when used)
        self.modal_client = ModalWorkerClient()
        self.runpod_client = RunPodWorkerClient(runpod_api_key)
        
        # Health tracking
        self.provider_health = {
            WorkerProvider.AWS: True,
            WorkerProvider.MODAL: True,
            WorkerProvider.RUNPOD: True,
        }
        
        self.last_health_check = {}
        self.health_check_interval = timedelta(minutes=5)
        
        # Statistics
        self.stats = {
            "total_jobs": 0,
            "aws_jobs": 0,
            "modal_jobs": 0,
            "runpod_jobs": 0,
            "failovers": 0,
            "errors": 0,
            "total_generation_time": 0.0,
            "total_training_time": 0.0,
        }
        
        # Metrics collector
        self.metrics = get_metrics_collector()
        
        # WebSocket manager
        self.websocket = get_websocket_manager()
        
        logger.info(
            f"Worker Manager initialized "
            f"(primary: {primary_provider.value}, fallback: {fallback_provider.value})"
        )
    
    async def generate(
        self,
        prompt: str,
        negative_prompt: str,
        identity_data: Dict,
        mode: str,
        config: Dict,
        user_id: str,
        generation_id: str,
        progress_callback: Optional[callable] = None,
    ) -> Dict:
        """
        Generate image using available GPU worker
        
        Automatically handles failover and progress updates.
        
        Args:
            prompt: Generation prompt
            negative_prompt: Negative prompt
            identity_data: Identity/LoRA data
            mode: Generation mode
            config: Generation configuration
            user_id: User ID
            generation_id: Generation job ID
            progress_callback: Optional callback for progress updates
            
        Returns:
            Result dictionary with success status and image URLs
        """
        import time
        import uuid
        start_time = time.time()
        
        self.stats["total_jobs"] += 1
        
        # Create job ID if not provided
        job_id = generation_id or str(uuid.uuid4())
        
        # Record metrics start
        provider_enum = await self._select_provider_enum()
        job_metrics = self.metrics.record_job_start(
            job_id=job_id,
            job_type=JobType.GENERATION,
            provider=provider_enum,
            user_id=user_id,
            metadata={"mode": mode, "num_candidates": config.get("num_candidates", 4)},
        )
        
        # Check health
        await self._check_health_if_needed()
        
        # Determine provider (cost-aware selection)
        provider = await self._select_provider(cost_aware=True, job_type="generation")
        
        logger.info(f"Using {provider.value} for generation {generation_id}")
        
        # Send WebSocket update
        await self._send_progress_update(
            user_id, generation_id, 0,
            f"Starting generation with {provider.value}...",
            progress_callback
        )
        
        # Try primary provider
        result = await self._generate_with_provider(
            provider,
            prompt,
            negative_prompt,
            identity_data,
            mode,
            config,
            user_id,
            generation_id,
        )
        
        # If failed and fallback available, try fallback
        if not result.get("success") and self.fallback_provider:
            logger.warning(
                f"{provider.value} failed, trying {self.fallback_provider.value}"
            )
            
            self.stats["failovers"] += 1
            
            if progress_callback:
                try:
                    await progress_callback(
                        0, f"Retrying with {self.fallback_provider.value}..."
                    )
                except Exception:
                    pass
            
            result = await self._generate_with_provider(
                self.fallback_provider,
                prompt,
                negative_prompt,
                identity_data,
                mode,
                config,
                user_id,
                generation_id,
            )
        
        # Update statistics
        generation_time = time.time() - start_time
        self.stats["total_generation_time"] += generation_time
        
        # Record metrics end
        self.metrics.record_job_end(
            job_id=job_id,
            success=result.get("success", False),
            error=result.get("error"),
            metadata={
                "generation_time": generation_time,
                "num_images": len(result.get("image_urls", [])),
            }
        )
        
        if not result.get("success"):
            self.stats["errors"] += 1
        
        # Final progress callback and WebSocket update
        status = "completed" if result.get("success") else "failed"
        await self._send_progress_update(
            user_id, generation_id, 100,
            f"Generation {status}",
            progress_callback
        )
        
        return result
    
    async def train(
        self,
        user_id: str,
        identity_id: str,
        photo_urls: List[str],
        config: Dict,
        progress_callback: Optional[callable] = None,
    ) -> Dict:
        """
        Train LoRA using available GPU worker
        
        Automatically handles failover and progress updates.
        
        Args:
            user_id: User ID
            identity_id: Identity ID
            photo_urls: List of photo S3 URLs
            config: Training configuration
            progress_callback: Optional callback for progress updates
            
        Returns:
            Result dictionary with success status and LoRA path
        """
        import time
        import uuid
        start_time = time.time()
        
        self.stats["total_jobs"] += 1
        
        # Create job ID
        job_id = identity_id or str(uuid.uuid4())
        
        # Record metrics start
        provider_enum = await self._select_provider_enum()
        job_metrics = self.metrics.record_job_start(
            job_id=job_id,
            job_type=JobType.TRAINING,
            provider=provider_enum,
            user_id=user_id,
            metadata={"num_photos": len(photo_urls)},
        )
        
        await self._check_health_if_needed()
        
        provider = await self._select_provider(cost_aware=True, job_type="training")
        
        logger.info(f"Using {provider.value} for training {identity_id}")
        
        # Send WebSocket update
        await self._send_training_progress_update(
            user_id, identity_id, 0,
            f"Starting training with {provider.value}...",
            progress_callback
        )
        
        # Try primary
        result = await self._train_with_provider(
            provider,
            user_id,
            identity_id,
            photo_urls,
            config,
        )
        
        # Fallback if failed
        if not result.get("success") and self.fallback_provider:
            logger.warning(
                f"{provider.value} failed, trying {self.fallback_provider.value}"
            )
            
            self.stats["failovers"] += 1
            
            if progress_callback:
                try:
                    await progress_callback(
                        0, f"Retrying with {self.fallback_provider.value}..."
                    )
                except Exception:
                    pass
            
            result = await self._train_with_provider(
                self.fallback_provider,
                user_id,
                identity_id,
                photo_urls,
                config,
            )
        
        # Update statistics
        training_time = time.time() - start_time
        self.stats["total_training_time"] += training_time
        
        # Record metrics end
        self.metrics.record_job_end(
            job_id=job_id,
            success=result.get("success", False),
            error=result.get("error"),
            metadata={
                "training_time": training_time,
                "lora_path": result.get("lora_path"),
            }
        )
        
        if not result.get("success"):
            self.stats["errors"] += 1
        
        # Final progress callback and WebSocket update
        status = "completed" if result.get("success") else "failed"
        await self._send_training_progress_update(
            user_id, identity_id, 100,
            f"Training {status}",
            progress_callback
        )
        
        return result
    
    async def _send_training_progress_update(
        self,
        user_id: str,
        identity_id: str,
        progress: int,
        message: str,
        progress_callback: Optional[callable] = None,
    ):
        """Send training progress update via WebSocket and callback"""
        # WebSocket update
        try:
            await self.websocket.send_training_progress(
                user_id=user_id,
                identity_id=identity_id,
                progress=progress,
                message=message,
            )
        except Exception as e:
            logger.warning(f"WebSocket update failed: {e}")
        
        # Callback update
        if progress_callback:
            try:
                await progress_callback(progress, message)
            except Exception as e:
                logger.warning(f"Progress callback failed: {e}")
    
    async def _generate_with_provider(
        self,
        provider: WorkerProvider,
        prompt: str,
        negative_prompt: str,
        identity_data: Dict,
        mode: str,
        config: Dict,
        user_id: str,
        generation_id: str,
    ) -> Dict:
        """Generate with specific provider"""
        try:
            if provider == WorkerProvider.AWS:
                self.stats["aws_jobs"] += 1
                from app.services.gpu_client import get_gpu_client
                client = get_gpu_client()
                result = await client.generate_with_safety(
                    user_id=user_id,
                    identity_id=identity_data.get("identity_id", "default"),
                    prompt=prompt,
                    mode=mode,
                    num_candidates=config.get("num_candidates", 4),
                    guidance_scale=config.get("guidance_scale", 7.5),
                    num_inference_steps=config.get("num_inference_steps", 40),
                    seed=config.get("seed"),
                    face_embedding=identity_data.get("face_embedding"),
                )
                return result
            
            if provider == WorkerProvider.MODAL:
                self.stats["modal_jobs"] += 1
                return await self.modal_client.generate(
                    prompt, negative_prompt, identity_data,
                    mode, config, user_id, generation_id
                )
            
            if provider == WorkerProvider.RUNPOD:
                if not self.runpod_client.available:
                    return {"success": False, "error": "RunPod not configured"}
                self.stats["runpod_jobs"] += 1
                return await self.runpod_client.generate(
                    prompt, negative_prompt, identity_data,
                    mode, config, user_id, generation_id
                )
            
            return {"success": False, "error": f"Unknown provider: {provider}"}
                
        except Exception as e:
            logger.error(f"Generation with {provider.value} failed: {e}", exc_info=True)
            self.provider_health[provider] = False
            return {"success": False, "error": str(e)}
    
    async def _train_with_provider(
        self,
        provider: WorkerProvider,
        user_id: str,
        identity_id: str,
        photo_urls: List[str],
        config: Dict,
    ) -> Dict:
        """Train with specific provider"""
        try:
            if provider == WorkerProvider.AWS:
                from app.services.gpu_client import get_gpu_client
                client = get_gpu_client()
                return await client.train_lora(
                    user_id=user_id,
                    identity_id=identity_id,
                    image_urls=photo_urls,
                    trigger_word=config.get("trigger_word", "sks"),
                    training_steps=config.get("training_steps", 1000),
                )
            
            if provider == WorkerProvider.MODAL:
                return await self.modal_client.train(
                    user_id, identity_id, photo_urls, config
                )
            
            if provider == WorkerProvider.RUNPOD:
                if not self.runpod_client.available:
                    return {"success": False, "error": "RunPod not configured"}
                return await self.runpod_client.train(
                    user_id, identity_id, photo_urls, config
                )
            
            return {"success": False, "error": f"Unknown provider: {provider}"}
                
        except Exception as e:
            logger.error(f"Training with {provider.value} failed: {e}", exc_info=True)
            self.provider_health[provider] = False
            return {"success": False, "error": str(e)}
    
    async def _select_provider_enum(self) -> ProviderType:
        """Convert WorkerProvider to ProviderType enum"""
        provider = await self._select_provider()
        if provider == WorkerProvider.AWS:
            return ProviderType.AWS
        if provider == WorkerProvider.MODAL:
            return ProviderType.MODAL
        return ProviderType.RUNPOD
    
    async def _select_provider(
        self,
        cost_aware: bool = False,
        job_type: str = "generation",
    ) -> WorkerProvider:
        """
        Select best available provider
        
        Logic:
        1. Use primary if healthy
        2. Use fallback if primary unhealthy
        3. If cost_aware, compare costs and select cheaper option
        4. Default to primary if both unhealthy (will fail gracefully)
        """
        # Cost-aware selection (when not AWS primary)
        if cost_aware and self.primary_provider != WorkerProvider.AWS:
            modal_stats = self.metrics.get_provider_statistics(ProviderType.MODAL)
            runpod_stats = self.metrics.get_provider_statistics(ProviderType.RUNPOD)
            if modal_stats["total_jobs"] > 10 and runpod_stats["total_jobs"] > 10:
                modal_healthy = self.provider_health.get(WorkerProvider.MODAL, False)
                runpod_healthy = self.provider_health.get(WorkerProvider.RUNPOD, False)
                if modal_healthy and runpod_healthy:
                    if runpod_stats["avg_cost"] < modal_stats["avg_cost"] * 0.9:
                        logger.info("Cost-aware: Selecting RunPod (cheaper)")
                        return WorkerProvider.RUNPOD
                    logger.info("Cost-aware: Selecting Modal")
                    return WorkerProvider.MODAL
        
        # Standard health-based selection
        if self.provider_health.get(self.primary_provider, False):
            return self.primary_provider
        
        if self.fallback_provider and self.provider_health.get(self.fallback_provider, False):
            logger.warning(
                f"Primary {self.primary_provider.value} unhealthy, "
                f"using {self.fallback_provider.value}"
            )
            return self.fallback_provider
        
        logger.warning("All providers unhealthy, using primary anyway")
        return self.primary_provider
    
    async def _send_progress_update(
        self,
        user_id: str,
        job_id: str,
        progress: int,
        message: str,
        progress_callback: Optional[callable] = None,
    ):
        """Send progress update via WebSocket and callback"""
        # WebSocket update
        try:
            await self.websocket.send_generation_progress(
                user_id=user_id,
                generation_id=job_id,
                progress=progress,
                message=message,
            )
        except Exception as e:
            logger.warning(f"WebSocket update failed: {e}")
        
        # Callback update
        if progress_callback:
            try:
                await progress_callback(progress, message)
            except Exception as e:
                logger.warning(f"Progress callback failed: {e}")
    
    async def _check_health_if_needed(self):
        """Check provider health if not checked recently"""
        now = datetime.utcnow()
        
        for provider in [self.primary_provider, self.fallback_provider]:
            if not provider:
                continue
            
            last_check = self.last_health_check.get(provider)
            
            if not last_check or (now - last_check) > self.health_check_interval:
                await self._check_provider_health(provider)
                self.last_health_check[provider] = now
    
    async def _check_provider_health(self, provider: WorkerProvider):
        """Check specific provider health"""
        try:
            if provider == WorkerProvider.AWS:
                healthy = True  # AWS client has no health endpoint; assume healthy when configured
            elif provider == WorkerProvider.MODAL:
                healthy = await self.modal_client.health_check()
            elif provider == WorkerProvider.RUNPOD:
                healthy = await self.runpod_client.health_check() if self.runpod_client else False
            else:
                healthy = False
            
            self.provider_health[provider] = healthy
            
            status = "✓" if healthy else "✗"
            logger.info(f"{status} {provider.value} health: {healthy}")
            
        except Exception as e:
            logger.error(f"Health check failed for {provider.value}: {e}")
            self.provider_health[provider] = False
    
    def get_statistics(self) -> Dict:
        """Get worker statistics"""
        total_jobs = self.stats["aws_jobs"] + self.stats["modal_jobs"] + self.stats["runpod_jobs"]
        avg_generation_time = (
            self.stats["total_generation_time"] / total_jobs if total_jobs > 0 else 0.0
        )
        
        # Get metrics
        metrics_stats = self.metrics.get_overall_statistics()
        
        return {
            **self.stats,
            "average_generation_time": avg_generation_time,
            "provider_health": {
                k.value: v for k, v in self.provider_health.items()
            },
            "primary_provider": self.primary_provider.value,
            "fallback_provider": self.fallback_provider.value if self.fallback_provider else None,
            "metrics": metrics_stats,
        }


# ==================== GLOBAL INSTANCE ====================

_worker_manager: Optional[WorkerManager] = None


def get_worker_manager() -> WorkerManager:
    """Get or create worker manager singleton"""
    global _worker_manager
    if _worker_manager is None:
        _worker_manager = WorkerManager()
    return _worker_manager
