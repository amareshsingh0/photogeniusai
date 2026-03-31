"""
GPU Workers Package

Production-grade GPU worker integration for PhotoGenius AI.
Supports Modal.com and RunPod with automatic failover.
"""

from .modal_worker import ModalWorkerClient
from .runpod_worker import RunPodWorkerClient
from .worker_manager import WorkerManager, WorkerProvider, get_worker_manager
from .task_queue import TaskQueue, TaskStatus, Task, get_task_queue
from .metrics import MetricsCollector, JobType, ProviderType, get_metrics_collector

__all__ = [
    # Clients
    "ModalWorkerClient",
    "RunPodWorkerClient",
    
    # Manager
    "WorkerManager",
    "WorkerProvider",
    "get_worker_manager",
    
    # Task Queue
    "TaskQueue",
    "TaskStatus",
    "Task",
    "get_task_queue",
    
    # Metrics
    "MetricsCollector",
    "JobType",
    "ProviderType",
    "get_metrics_collector",
]
]
