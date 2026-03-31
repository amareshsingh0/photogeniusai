"""
Tests for Worker Manager

Tests worker management, failover, and health checks.
"""

import pytest  # type: ignore[reportMissingImports]
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timedelta

from app.workers.worker_manager import (
    WorkerManager,
    WorkerProvider,
    get_worker_manager,
)
from app.workers.task_queue import TaskQueue, TaskStatus, get_task_queue


class TestWorkerManager:
    """Tests for worker manager (AWS primary by default)."""

    @pytest.fixture
    def manager(self):
        """Create worker manager with Modal primary (for failover tests)."""
        return WorkerManager(
            primary_provider=WorkerProvider.MODAL,
            fallback_provider=WorkerProvider.RUNPOD,
        )

    @pytest.fixture
    def manager_aws(self):
        """Create worker manager with AWS primary (default)."""
        return WorkerManager(primary_provider=WorkerProvider.AWS)

    def test_initialize_manager(self, manager):
        """Test manager initialization with Modal primary"""
        assert manager is not None
        assert manager.primary_provider == WorkerProvider.MODAL
        assert manager.fallback_provider == WorkerProvider.RUNPOD

    def test_default_primary_is_aws(self, manager_aws):
        """Test that default primary provider is AWS"""
        assert manager_aws.primary_provider == WorkerProvider.AWS
        assert manager_aws.fallback_provider is None

    def test_statistics(self, manager):
        """Test statistics retrieval"""
        stats = manager.get_statistics()

        assert "total_jobs" in stats
        assert "aws_jobs" in stats
        assert "modal_jobs" in stats
        assert "runpod_jobs" in stats
        assert "failovers" in stats
        assert "errors" in stats
        assert "provider_health" in stats

    @pytest.mark.asyncio
    async def test_health_check(self, manager):
        """Test health checking"""
        manager.modal_client.health_check = AsyncMock(return_value=True)
        manager.runpod_client.health_check = AsyncMock(return_value=True)

        await manager._check_provider_health(WorkerProvider.AWS)
        await manager._check_provider_health(WorkerProvider.MODAL)
        await manager._check_provider_health(WorkerProvider.RUNPOD)

        assert manager.provider_health[WorkerProvider.AWS] is True
        assert manager.provider_health[WorkerProvider.MODAL] is True
        assert manager.provider_health[WorkerProvider.RUNPOD] is True

    @pytest.mark.asyncio
    async def test_provider_selection(self, manager):
        """Test provider selection logic"""
        # Set health
        manager.provider_health[WorkerProvider.MODAL] = True
        manager.provider_health[WorkerProvider.RUNPOD] = True

        # Should select primary
        provider = await manager._select_provider()
        assert provider == WorkerProvider.MODAL

        # If primary unhealthy, should select fallback
        manager.provider_health[WorkerProvider.MODAL] = False
        provider = await manager._select_provider()
        assert provider == WorkerProvider.RUNPOD

    @pytest.mark.asyncio
    async def test_generate_with_failover(self, manager):
        """Test generation with automatic failover"""
        # Mock clients
        manager.modal_client.generate = AsyncMock(
            return_value={"success": False, "error": "Modal failed"}
        )
        manager.runpod_client.generate = AsyncMock(
            return_value={"success": True, "image_urls": ["url1", "url2"]}
        )
        manager.runpod_client.available = True

        # Set health
        manager.provider_health[WorkerProvider.MODAL] = True
        manager.provider_health[WorkerProvider.RUNPOD] = True

        result = await manager.generate(
            prompt="test prompt",
            negative_prompt="test negative",
            identity_data={},
            mode="REALISM",
            config={},
            user_id="user123",
            generation_id="gen123",
        )

        # Should succeed after failover
        assert result["success"] is True
        assert "image_urls" in result
        assert manager.stats["failovers"] == 1

    @pytest.mark.asyncio
    async def test_train_with_failover(self, manager):
        """Test training with automatic failover"""
        # Mock clients
        manager.modal_client.train = AsyncMock(
            return_value={"success": False, "error": "Modal failed"}
        )
        manager.runpod_client.train = AsyncMock(
            return_value={"success": True, "lora_path": "s3://bucket/lora.safetensors"}
        )
        manager.runpod_client.available = True

        # Set health
        manager.provider_health[WorkerProvider.MODAL] = True
        manager.provider_health[WorkerProvider.RUNPOD] = True

        result = await manager.train(
            user_id="user123",
            identity_id="identity123",
            photo_urls=["s3://bucket/photo1.jpg"],
            config={},
        )

        # Should succeed after failover
        assert result["success"] is True
        assert "lora_path" in result
        assert manager.stats["failovers"] == 1


class TestTaskQueue:
    """Tests for task queue"""

    @pytest.fixture
    def queue(self):
        """Create task queue instance"""
        return TaskQueue(max_concurrent=5)

    def test_initialize_queue(self, queue):
        """Test queue initialization"""
        assert queue is not None
        assert queue.max_concurrent == 5
        assert queue.running == 0

    @pytest.mark.asyncio
    async def test_submit_task(self, queue):
        """Test task submission"""
        task_id = await queue.submit(
            task_type="generation",
            payload={"prompt": "test"},
            user_id="user123",
        )

        assert task_id is not None
        assert task_id in queue.tasks

        task = queue.tasks[task_id]
        assert task.type == "generation"
        assert task.status == TaskStatus.PENDING
        assert task.user_id == "user123"

    @pytest.mark.asyncio
    async def test_get_status(self, queue):
        """Test getting task status"""
        task_id = await queue.submit(
            task_type="generation",
            payload={"prompt": "test"},
        )

        task = await queue.get_status(task_id)
        assert task is not None
        assert task.id == task_id
        assert task.status == TaskStatus.PENDING

    @pytest.mark.asyncio
    async def test_cancel_task(self, queue):
        """Test task cancellation"""
        task_id = await queue.submit(
            task_type="generation",
            payload={"prompt": "test"},
        )

        cancelled = await queue.cancel(task_id)
        assert cancelled is True

        task = queue.tasks[task_id]
        assert task.status == TaskStatus.CANCELLED

    def test_statistics(self, queue):
        """Test queue statistics"""
        stats = queue.get_statistics()

        assert "total_tasks" in stats
        assert "pending" in stats
        assert "running" in stats
        assert "completed" in stats
        assert "failed" in stats
        assert "max_concurrent" in stats

    @pytest.mark.asyncio
    async def test_start_stop(self, queue):
        """Test starting and stopping queue"""
        await queue.start()
        assert queue._running is True
        assert queue.worker_task is not None

        await queue.stop()
        assert queue._running is False


class TestWorkerIntegration:
    """Integration tests for worker system"""

    @pytest.mark.asyncio
    async def test_get_worker_manager_singleton(self):
        """Test worker manager singleton"""
        manager1 = get_worker_manager()
        manager2 = get_worker_manager()

        assert manager1 is manager2

    @pytest.mark.asyncio
    async def test_get_task_queue_singleton(self):
        """Test task queue singleton"""
        queue1 = get_task_queue()
        queue2 = get_task_queue()

        assert queue1 is queue2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
