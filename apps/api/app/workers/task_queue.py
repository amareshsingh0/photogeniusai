"""
Task Queue for GPU Jobs

Manages queuing and execution of GPU tasks with concurrency control,
progress tracking, and WebSocket support.
"""

import asyncio
from typing import Dict, Optional, Callable, Any
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import logging
import uuid

logger = logging.getLogger(__name__)


class TaskStatus(Enum):
    """Task status"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class Task:
    """GPU task"""
    id: str
    type: str  # "generation" or "training"
    payload: Dict
    status: TaskStatus
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    result: Optional[Dict] = None
    error: Optional[str] = None
    progress: int = 0
    progress_message: str = ""
    user_id: Optional[str] = None
    metadata: Dict = field(default_factory=dict)


class TaskQueue:
    """
    Task queue for GPU jobs
    
    Features:
    - Concurrency control
    - Progress tracking
    - WebSocket support
    - Statistics
    - Error handling
    """
    
    def __init__(self, max_concurrent: int = 10):
        """
        Initialize task queue
        
        Args:
            max_concurrent: Max concurrent GPU tasks
        """
        self.max_concurrent = max_concurrent
        self.tasks: Dict[str, Task] = {}
        self.pending_queue = asyncio.Queue()
        self.running = 0
        self.semaphore = asyncio.Semaphore(max_concurrent)
        
        # Start worker
        self.worker_task: Optional[asyncio.Task] = None
        self._running = False
        
        logger.info(f"Task Queue initialized (max concurrent: {max_concurrent})")
    
    async def start(self):
        """Start queue worker"""
        if not self._running:
            self._running = True
            self.worker_task = asyncio.create_task(self._worker())
            logger.info("Task Queue worker started")
    
    async def stop(self):
        """Stop queue worker"""
        if self._running:
            self._running = False
            if self.worker_task:
                self.worker_task.cancel()
                try:
                    await self.worker_task
                except asyncio.CancelledError:
                    pass
            logger.info("Task Queue worker stopped")
    
    async def submit(
        self,
        task_type: str,
        payload: Dict,
        user_id: Optional[str] = None,
        callback: Optional[Callable] = None,
        metadata: Optional[Dict] = None,
    ) -> str:
        """
        Submit task to queue
        
        Args:
            task_type: "generation" or "training"
            payload: Task payload
            user_id: User ID (optional)
            callback: Optional progress callback
            metadata: Optional task metadata
            
        Returns:
            Task ID
        """
        task_id = str(uuid.uuid4())
        
        task = Task(
            id=task_id,
            type=task_type,
            payload=payload,
            status=TaskStatus.PENDING,
            created_at=datetime.utcnow(),
            user_id=user_id,
            metadata=metadata or {},
        )
        
        self.tasks[task_id] = task
        
        await self.pending_queue.put((task, callback))
        
        logger.info(f"Task {task_id} ({task_type}) submitted")
        
        return task_id
    
    async def get_status(self, task_id: str) -> Optional[Task]:
        """Get task status"""
        return self.tasks.get(task_id)
    
    async def cancel(self, task_id: str) -> bool:
        """Cancel pending task"""
        task = self.tasks.get(task_id)
        
        if task and task.status == TaskStatus.PENDING:
            task.status = TaskStatus.CANCELLED
            logger.info(f"Task {task_id} cancelled")
            return True
        
        return False
    
    async def _worker(self):
        """Background worker that processes queue"""
        while self._running:
            try:
                # Get next task (with timeout to allow checking _running)
                try:
                    task, callback = await asyncio.wait_for(
                        self.pending_queue.get(),
                        timeout=1.0
                    )
                except asyncio.TimeoutError:
                    continue
                
                # Acquire semaphore
                async with self.semaphore:
                    await self._execute_task(task, callback)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Worker error: {e}", exc_info=True)
    
    async def _execute_task(self, task: Task, callback: Optional[Callable]):
        """Execute single task"""
        if task.status == TaskStatus.CANCELLED:
            return
        
        task.status = TaskStatus.RUNNING
        task.started_at = datetime.utcnow()
        self.running += 1
        
        logger.info(f"Executing task {task.id} ({task.type})")
        
        try:
            # Import worker manager
            from .worker_manager import get_worker_manager
            
            manager = get_worker_manager()
            
            # Progress callback wrapper with WebSocket support
            async def progress_update(progress: int, message: str):
                task.progress = progress
                task.progress_message = message
                
                # Send WebSocket update if user_id available
                if task.user_id:
                    try:
                        from app.services.websocket.manager import get_websocket_manager
                        ws_manager = get_websocket_manager()
                        
                        if task.type == "generation":
                            await ws_manager.send_generation_progress(
                                user_id=task.user_id,
                                generation_id=task.payload.get("generation_id", task.id),
                                progress=progress,
                                message=message,
                            )
                        elif task.type == "training":
                            await ws_manager.send_training_progress(
                                user_id=task.user_id,
                                identity_id=task.payload.get("identity_id", task.id),
                                progress=progress,
                                message=message,
                            )
                    except Exception as e:
                        logger.warning(f"WebSocket update failed: {e}")
                
                # Call custom callback if provided
                if callback:
                    try:
                        await callback(task.id, progress, message, task)
                    except Exception as e:
                        logger.error(f"Progress callback failed: {e}")
            
            # Execute based on type
            if task.type == "generation":
                task.payload["progress_callback"] = progress_update
                result = await manager.generate(**task.payload)
            
            elif task.type == "training":
                task.payload["progress_callback"] = progress_update
                result = await manager.train(**task.payload)
            
            else:
                raise ValueError(f"Unknown task type: {task.type}")
            
            # Update task
            if result.get("success"):
                task.status = TaskStatus.COMPLETED
                task.result = result
            else:
                task.status = TaskStatus.FAILED
                task.error = result.get("error", "Unknown error")
            
        except Exception as e:
            logger.error(f"Task {task.id} failed: {e}", exc_info=True)
            task.status = TaskStatus.FAILED
            task.error = str(e)
        
        finally:
            task.completed_at = datetime.utcnow()
            self.running -= 1
            
            logger.info(f"Task {task.id} completed: {task.status.value}")
    
    def get_statistics(self) -> Dict:
        """Get queue statistics"""
        completed = sum(
            1 for t in self.tasks.values()
            if t.status == TaskStatus.COMPLETED
        )
        failed = sum(
            1 for t in self.tasks.values()
            if t.status == TaskStatus.FAILED
        )
        pending = sum(
            1 for t in self.tasks.values()
            if t.status == TaskStatus.PENDING
        )
        
        return {
            "total_tasks": len(self.tasks),
            "pending": pending,
            "running": self.running,
            "completed": completed,
            "failed": failed,
            "max_concurrent": self.max_concurrent,
            "queue_size": self.pending_queue.qsize(),
        }
    
    def cleanup_old_tasks(self, max_age_hours: int = 24):
        """
        Clean up old completed/failed tasks
        
        Args:
            max_age_hours: Maximum age in hours for tasks to keep
        """
        cutoff = datetime.utcnow() - timedelta(hours=max_age_hours)
        
        to_remove = [
            task_id for task_id, task in self.tasks.items()
            if task.completed_at and task.completed_at < cutoff
            and task.status in [TaskStatus.COMPLETED, TaskStatus.FAILED]
        ]
        
        for task_id in to_remove:
            del self.tasks[task_id]
        
        if to_remove:
            logger.info(f"Cleaned up {len(to_remove)} old tasks")


# ==================== GLOBAL INSTANCE ====================

_task_queue: Optional[TaskQueue] = None


def get_task_queue(max_concurrent: int = 10) -> TaskQueue:
    """Get or create task queue singleton"""
    global _task_queue
    if _task_queue is None:
        _task_queue = TaskQueue(max_concurrent=max_concurrent)
    return _task_queue
