"""
Performance Metrics and Cost Tracking

Tracks GPU worker performance, costs, and optimization metrics.
"""

import logging
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
import time

logger = logging.getLogger(__name__)


class JobType(Enum):
    """Job type"""
    GENERATION = "generation"
    TRAINING = "training"


class ProviderType(Enum):
    """Provider type"""
    AWS = "aws"
    MODAL = "modal"
    RUNPOD = "runpod"


@dataclass
class JobMetrics:
    """Metrics for a single job"""
    job_id: str
    job_type: JobType
    provider: ProviderType
    user_id: str
    start_time: datetime
    end_time: Optional[datetime] = None
    duration_seconds: float = 0.0
    cost_usd: float = 0.0
    success: bool = False
    error: Optional[str] = None
    metadata: Dict = field(default_factory=dict)


class MetricsCollector:
    """
    Collects and analyzes GPU worker metrics
    
    Features:
    - Cost tracking per provider
    - Performance metrics
    - Success rate tracking
    - Cost optimization recommendations
    """
    
    # Cost per second (approximate)
    COST_PER_SECOND = {
        ProviderType.AWS: {
            JobType.GENERATION: 0.00012,  # SageMaker/Lambda
            JobType.TRAINING: 0.00020,
        },
        ProviderType.MODAL: {
            JobType.GENERATION: 0.00015,  # ~$0.15/hour for A100
            JobType.TRAINING: 0.00025,    # ~$0.25/hour for A100 training
        },
        ProviderType.RUNPOD: {
            JobType.GENERATION: 0.00012,  # Varies by GPU
            JobType.TRAINING: 0.00020,
        },
    }
    
    def __init__(self, max_history: int = 10000):
        """
        Initialize metrics collector
        
        Args:
            max_history: Maximum number of jobs to keep in history
        """
        self.max_history = max_history
        self.jobs: List[JobMetrics] = []
        self._lock = None  # Will be asyncio.Lock if needed
        
        logger.info("Metrics Collector initialized")
    
    def record_job_start(
        self,
        job_id: str,
        job_type: JobType,
        provider: ProviderType,
        user_id: str,
        metadata: Optional[Dict] = None,
    ) -> JobMetrics:
        """
        Record job start
        
        Returns:
            JobMetrics instance
        """
        metrics = JobMetrics(
            job_id=job_id,
            job_type=job_type,
            provider=provider,
            user_id=user_id,
            start_time=datetime.utcnow(),
            metadata=metadata or {},
        )
        
        self.jobs.append(metrics)
        
        # Trim history if needed
        if len(self.jobs) > self.max_history:
            self.jobs = self.jobs[-self.max_history:]
        
        return metrics
    
    def record_job_end(
        self,
        job_id: str,
        success: bool,
        error: Optional[str] = None,
        metadata: Optional[Dict] = None,
    ):
        """Record job completion"""
        for job in reversed(self.jobs):
            if job.job_id == job_id:
                job.end_time = datetime.utcnow()
                job.duration_seconds = (job.end_time - job.start_time).total_seconds()
                job.success = success
                job.error = error
                
                # Calculate cost
                cost_per_second = self.COST_PER_SECOND.get(job.provider, {}).get(job.job_type, 0.0)
                job.cost_usd = job.duration_seconds * cost_per_second
                
                if metadata:
                    job.metadata.update(metadata)
                
                break
    
    def get_provider_statistics(self, provider: ProviderType) -> Dict:
        """Get statistics for a provider"""
        provider_jobs = [j for j in self.jobs if j.provider == provider and j.end_time]
        
        if not provider_jobs:
            return {
                "total_jobs": 0,
                "success_rate": 0.0,
                "avg_duration": 0.0,
                "total_cost": 0.0,
                "avg_cost": 0.0,
            }
        
        successful = sum(1 for j in provider_jobs if j.success)
        total_duration = sum(j.duration_seconds for j in provider_jobs)
        total_cost = sum(j.cost_usd for j in provider_jobs)
        
        return {
            "total_jobs": len(provider_jobs),
            "success_rate": successful / len(provider_jobs) if provider_jobs else 0.0,
            "avg_duration": total_duration / len(provider_jobs),
            "total_cost": total_cost,
            "avg_cost": total_cost / len(provider_jobs),
            "successful_jobs": successful,
            "failed_jobs": len(provider_jobs) - successful,
        }
    
    def get_job_type_statistics(self, job_type: JobType) -> Dict:
        """Get statistics for a job type"""
        type_jobs = [j for j in self.jobs if j.job_type == job_type and j.end_time]
        
        if not type_jobs:
            return {
                "total_jobs": 0,
                "success_rate": 0.0,
                "avg_duration": 0.0,
                "total_cost": 0.0,
            }
        
        successful = sum(1 for j in type_jobs if j.success)
        total_duration = sum(j.duration_seconds for j in type_jobs)
        total_cost = sum(j.cost_usd for j in type_jobs)
        
        return {
            "total_jobs": len(type_jobs),
            "success_rate": successful / len(type_jobs),
            "avg_duration": total_duration / len(type_jobs),
            "total_cost": total_cost,
            "avg_cost": total_cost / len(type_jobs),
        }
    
    def get_cost_optimization_recommendations(self) -> List[Dict]:
        """Get cost optimization recommendations"""
        recommendations = []
        
        # Compare providers
        modal_stats = self.get_provider_statistics(ProviderType.MODAL)
        runpod_stats = self.get_provider_statistics(ProviderType.RUNPOD)
        
        if modal_stats["total_jobs"] > 10 and runpod_stats["total_jobs"] > 10:
            if modal_stats["avg_cost"] > runpod_stats["avg_cost"] * 1.2:
                recommendations.append({
                    "type": "provider_switch",
                    "message": f"RunPod is {((modal_stats['avg_cost'] / runpod_stats['avg_cost']) - 1) * 100:.1f}% cheaper",
                    "recommendation": "Consider using RunPod as primary provider",
                })
        
        # Check for long-running jobs
        recent_jobs = [j for j in self.jobs if j.end_time and (datetime.utcnow() - j.end_time) < timedelta(hours=24)]
        long_jobs = [j for j in recent_jobs if j.duration_seconds > 300]  # > 5 minutes
        
        if len(long_jobs) > len(recent_jobs) * 0.2:  # > 20% are long
            recommendations.append({
                "type": "optimization",
                "message": f"{len(long_jobs)} jobs took > 5 minutes",
                "recommendation": "Consider optimizing generation parameters or using faster models",
            })
        
        return recommendations
    
    def get_overall_statistics(self) -> Dict:
        """Get overall statistics"""
        completed_jobs = [j for j in self.jobs if j.end_time]
        
        if not completed_jobs:
            return {
                "total_jobs": 0,
                "total_cost": 0.0,
                "success_rate": 0.0,
                "providers": {},
            }
        
        total_cost = sum(j.cost_usd for j in completed_jobs)
        successful = sum(1 for j in completed_jobs if j.success)
        
        return {
            "total_jobs": len(completed_jobs),
            "total_cost": total_cost,
            "success_rate": successful / len(completed_jobs) if completed_jobs else 0.0,
            "providers": {
                ProviderType.AWS.value: self.get_provider_statistics(ProviderType.AWS),
                ProviderType.MODAL.value: self.get_provider_statistics(ProviderType.MODAL),
                ProviderType.RUNPOD.value: self.get_provider_statistics(ProviderType.RUNPOD),
            },
            "job_types": {
                JobType.GENERATION.value: self.get_job_type_statistics(JobType.GENERATION),
                JobType.TRAINING.value: self.get_job_type_statistics(JobType.TRAINING),
            },
            "recommendations": self.get_cost_optimization_recommendations(),
        }


# ==================== GLOBAL INSTANCE ====================

_metrics_collector: Optional[MetricsCollector] = None


def get_metrics_collector() -> MetricsCollector:
    """Get or create metrics collector singleton"""
    global _metrics_collector
    if _metrics_collector is None:
        _metrics_collector = MetricsCollector()
    return _metrics_collector
