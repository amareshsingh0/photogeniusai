# 🚀 GPU Workers Guide - PhotoGenius AI

## Overview

Production-grade GPU worker system supporting Modal.com and RunPod with automatic failover, health checks, and task queue management.

---

## 🏗️ Architecture

### Components

1. **ModalWorkerClient** (`modal_worker.py`)
   - Modal.com serverless GPU integration
   - A100 40GB GPU support
   - Auto-scaling and cost optimization

2. **RunPodWorkerClient** (`runpod_worker.py`)
   - RunPod GPU endpoint integration
   - Supports both serverless and dedicated pods
   - HTTP API-based

3. **WorkerManager** (`worker_manager.py`)
   - Automatic failover between providers
   - Health checking and monitoring
   - Statistics tracking
   - Progress callbacks

4. **TaskQueue** (`task_queue.py`)
   - Concurrency control
   - Progress tracking
   - WebSocket support
   - Task lifecycle management

---

## 📋 Configuration

### Environment Variables

Add to `apps/api/.env.local`:

```bash
# Modal.com Configuration
MODAL_TOKEN_ID=your_modal_token_id
MODAL_TOKEN_SECRET=your_modal_token_secret

# RunPod Configuration (Optional)
RUNPOD_API_KEY=your_runpod_api_key
RUNPOD_GENERATION_ENDPOINT=your_generation_endpoint_id
RUNPOD_TRAINING_ENDPOINT=your_training_endpoint_id

# Worker Configuration
GPU_WORKER_PRIMARY=modal  # or "runpod"
GPU_WORKER_FALLBACK=runpod  # or "modal"
TASK_QUEUE_MAX_CONCURRENT=10
```

---

## 🚀 Setup

### 1. Install Dependencies

```bash
cd apps/api
pip install -r requirements.txt
```

This installs:
- `modal==0.64.0` - Modal.com SDK
- `httpx` - Already included for RunPod API

### 2. Configure Modal.com

**Important: Run from `apps/api` folder!**

```powershell
# Navigate to API folder
cd "C:\desktop\PhotoGenius AI\apps\api"

# Install Modal CLI
pip install modal

# Login (creates token)
modal token new

# Deploy workers (path relative to apps/api)
modal deploy app/workers/modal_worker.py
```

**After `modal token new`, add credentials to `apps/api/.env.local`:**
```bash
MODAL_TOKEN_ID=your_token_id
MODAL_TOKEN_SECRET=your_token_secret
```

### 3. Configure RunPod (Optional)

1. Get API key from https://runpod.io
2. Create endpoints for generation and training
3. Set endpoint IDs in environment variables

---

## 💻 Usage

### Basic Usage

```python
from app.workers import get_worker_manager

# Get worker manager
manager = get_worker_manager()

# Generate image
result = await manager.generate(
    prompt="a beautiful sunset",
    negative_prompt="blurry, low quality",
    identity_data={"lora_path": "s3://bucket/lora.safetensors"},
    mode="REALISM",
    config={
        "num_candidates": 4,
        "num_inference_steps": 30,
        "guidance_scale": 7.5,
    },
    user_id="user123",
    generation_id="gen123",
)

if result["success"]:
    print(f"Generated {len(result['image_urls'])} images")
    for url in result["image_urls"]:
        print(f"  - {url}")
```

### With Progress Callbacks

```python
async def progress_callback(progress: int, message: str):
    print(f"Progress: {progress}% - {message}")

result = await manager.generate(
    prompt="test",
    negative_prompt="",
    identity_data={},
    mode="REALISM",
    config={},
    user_id="user123",
    generation_id="gen123",
    progress_callback=progress_callback,
)
```

### Using Task Queue

```python
from app.workers import get_task_queue

# Get task queue
queue = get_task_queue()

# Start queue worker
await queue.start()

# Submit task
task_id = await queue.submit(
    task_type="generation",
    payload={
        "prompt": "test",
        "negative_prompt": "",
        "identity_data": {},
        "mode": "REALISM",
        "config": {},
        "user_id": "user123",
        "generation_id": "gen123",
    },
    user_id="user123",
)

# Check status
task = await queue.get_status(task_id)
print(f"Status: {task.status.value}")
print(f"Progress: {task.progress}%")
```

### LoRA Training

```python
result = await manager.train(
    user_id="user123",
    identity_id="identity123",
    photo_urls=[
        "s3://bucket/photo1.jpg",
        "s3://bucket/photo2.jpg",
        # ... more photos
    ],
    config={
        "training_steps": 1000,
        "learning_rate": 1e-4,
    },
)

if result["success"]:
    print(f"LoRA trained: {result['lora_path']}")
```

---

## 🔍 Monitoring

### Statistics

```python
# Worker manager statistics
stats = manager.get_statistics()
print(f"Total jobs: {stats['total_jobs']}")
print(f"Modal jobs: {stats['modal_jobs']}")
print(f"RunPod jobs: {stats['runpod_jobs']}")
print(f"Failovers: {stats['failovers']}")
print(f"Provider health: {stats['provider_health']}")

# Task queue statistics
queue_stats = queue.get_statistics()
print(f"Pending: {queue_stats['pending']}")
print(f"Running: {queue_stats['running']}")
print(f"Completed: {queue_stats['completed']}")
```

### Health Checks

Health checks run automatically every 5 minutes. You can also trigger manually:

```python
await manager._check_provider_health(WorkerProvider.MODAL)
await manager._check_provider_health(WorkerProvider.RUNPOD)
```

---

## 🔄 Failover

The system automatically handles failover:

1. **Primary provider fails** → Automatically switches to fallback
2. **Health checks** → Monitors provider availability
3. **Statistics** → Tracks failover events

Example:
```python
# If Modal fails, automatically uses RunPod
result = await manager.generate(...)
# System handles failover transparently
```

---

## 🧪 Testing

**Run from `apps/api` folder:**

```powershell
# Navigate to API folder
cd "C:\desktop\PhotoGenius AI\apps\api"

# Run tests
pytest app/tests/test_worker_manager.py -v
```

**See `docs/WORKERS_SETUP_COMMANDS.md` for detailed setup instructions.**

---

## 📊 Performance

### Modal.com
- **GPU**: A100 40GB
- **Memory**: 16GB (generation), 32GB (training)
- **CPU**: 8 vCPUs (generation), 16 vCPUs (training)
- **Auto-scaling**: Yes
- **Cost**: Pay-per-use

### RunPod
- **GPU**: Configurable (A100, RTX 4090, etc.)
- **Dedicated**: Yes (for training)
- **Serverless**: Yes (for generation)
- **Cost**: Varies by GPU type

---

## 🛠️ Troubleshooting

### Modal Not Available

1. Check credentials:
   ```bash
   modal token list
   ```

2. Verify deployment:
   ```bash
   modal app list
   ```

3. Check logs:
   ```bash
   modal app logs photogenius-ai-workers
   ```

### RunPod Not Available

1. Verify API key:
   ```python
   client = RunPodWorkerClient()
   healthy = await client.health_check()
   ```

2. Check endpoint IDs:
   - Verify `RUNPOD_GENERATION_ENDPOINT`
   - Verify `RUNPOD_TRAINING_ENDPOINT`

### Task Queue Issues

1. Check queue status:
   ```python
   stats = queue.get_statistics()
   print(stats)
   ```

2. Clean up old tasks:
   ```python
   queue.cleanup_old_tasks(max_age_hours=24)
   ```

---

## 📝 Notes

- **Modal.com** is recommended for production (auto-scaling, cost-effective)
- **RunPod** is good for dedicated GPU workloads
- **Failover** happens automatically - no manual intervention needed
- **Progress callbacks** can be used for WebSocket updates
- **Task queue** manages concurrency and prevents overload

---

## 🔗 Links

- [Modal.com Documentation](https://modal.com/docs)
- [RunPod API Documentation](https://docs.runpod.io/serverless/endpoints)
- [PhotoGenius AI Documentation](./README.md)

---

**Last Updated**: After implementing production-grade GPU worker system
