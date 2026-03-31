# Monitoring Integration Guide

How to integrate monitoring logging into your services.

## Quick Integration

### Step 1: Add Logger Import

```python
from ai_pipeline.monitoring.logger import log_generation
import time
```

### Step 2: Log After Generation

Add logging after successful/failed generation:

```python
# In orchestrator.py, after _execute_plan():
start_time = time.time()

try:
    candidates = self._execute_plan(...)
    elapsed_time = time.time() - start_time
    
    # Log successful generation
    for i, candidate in enumerate(candidates):
        log_generation(
            user_id=user_id or "anonymous",
            generation_id=f"{job_id}_{i}",
            mode=mode,
            time_seconds=elapsed_time,
            status="completed",
            similarity=candidate.get("scores", {}).get("face_similarity"),
            quality_score=candidate.get("scores", {}).get("total"),
            cost=estimate_cost(elapsed_time, mode),
            identity_id=identity_id,
        )
except Exception as e:
    elapsed_time = time.time() - start_time
    
    # Log failed generation
    log_generation(
        user_id=user_id or "anonymous",
        generation_id=job_id,
        mode=mode,
        time_seconds=elapsed_time,
        status="failed",
        error_type=type(e).__name__,
        cost=estimate_cost(elapsed_time, mode),
    )
```

### Step 3: Cost Estimation Helper

Add cost estimation function:

```python
def estimate_cost(time_seconds: float, mode: str) -> float:
    """Estimate generation cost"""
    # Base cost: A10G GPU ~$0.10/hour = $0.000028/second
    base_cost_per_second = 0.000028
    
    # Mode multipliers (higher quality = more cost)
    multipliers = {
        "REALISM": 1.0,
        "CREATIVE": 1.2,
        "ROMANTIC": 1.1,
        "FASHION": 1.15,
        "CINEMATIC": 1.3,
    }
    
    multiplier = multipliers.get(mode, 1.0)
    return time_seconds * base_cost_per_second * multiplier
```

## Complete Example

### Orchestrator Integration

```python
# In orchestrator.py _execute_plan() method:

import time
from ai_pipeline.monitoring.logger import log_generation

def _execute_plan(self, ...):
    start_time = time.time()
    
    try:
        # ... existing generation code ...
        candidates = self.identity_engine_generate.remote(...)
        
        elapsed_time = time.time() - start_time
        
        # Log each candidate
        for i, candidate in enumerate(candidates):
            log_generation(
                user_id=user_id or "orchestrator",
                generation_id=f"{identity_id or 'anon'}_{i}_{int(time.time())}",
                mode=mode,
                time_seconds=elapsed_time / len(candidates),  # Average per image
                status="completed",
                similarity=candidate.get("scores", {}).get("face_similarity"),
                quality_score=candidate.get("scores", {}).get("total"),
                cost=estimate_cost(elapsed_time / len(candidates), mode),
                identity_id=identity_id,
            )
        
        return candidates
    
    except Exception as e:
        elapsed_time = time.time() - start_time
        
        log_generation(
            user_id=user_id or "orchestrator",
            generation_id=f"failed_{int(time.time())}",
            mode=mode,
            time_seconds=elapsed_time,
            status="failed",
            error_type=type(e).__name__,
            cost=estimate_cost(elapsed_time, mode),
        )
        
        raise
```

### Refinement Engine Integration

```python
# In refinement_engine.py refine() method:

import time
from ai_pipeline.monitoring.logger import log_refinement

@modal.method()
def refine(self, ...):
    start_time = time.time()
    
    try:
        # ... existing refinement code ...
        result = self.pipe(...)
        
        elapsed_time = time.time() - start_time
        
        log_refinement(
            user_id=user_id or "anonymous",
            refinement_id=f"ref_{int(time.time())}",
            original_generation_id=generation_history[0].get("generation_id", "unknown"),
            time_seconds=elapsed_time,
            status="completed",
            cost=estimate_refinement_cost(elapsed_time),
        )
        
        return result
    
    except Exception as e:
        elapsed_time = time.time() - start_time
        
        log_refinement(
            user_id=user_id or "anonymous",
            refinement_id=f"ref_{int(time.time())}",
            original_generation_id="unknown",
            time_seconds=elapsed_time,
            status="failed",
            cost=estimate_refinement_cost(elapsed_time),
        )
        
        raise

def estimate_refinement_cost(time_seconds: float) -> float:
    """Refinement uses A10G, similar cost"""
    return time_seconds * 0.000028
```

## User Rating Integration

When users rate images (thumbs up/down), log the rating:

```python
# In your API endpoint:
from ai_pipeline.monitoring.logger import log_generation

@app.post("/api/rate")
async def rate_image(generation_id: str, rating: str):
    # Update generation log with rating
    # Note: This requires updating the log entry
    # For now, log a new event with rating
    
    log_generation(
        user_id=user_id,
        generation_id=generation_id,
        mode="unknown",  # Not needed for rating
        time_seconds=0,
        status="completed",
        rating=rating,  # "up" or "down"
    )
```

## Testing

Test monitoring locally:

```python
from ai_pipeline.monitoring.logger import log_generation

# Test log
log_generation(
    user_id="test_user",
    generation_id="test_123",
    mode="REALISM",
    time_seconds=45.5,
    status="completed",
    similarity=0.95,
    quality_score=92.5,
    cost=0.0013,
    identity_id="test_identity",
)

# Check metrics collection
from ai_pipeline.monitoring.metrics import MetricsCollector
collector = MetricsCollector()
metrics = collector.collect_metrics.remote()
print(metrics)
```

## Verification

After integration:

1. **Check Logs Are Created:**
   ```bash
   modal volume ls photogenius-metrics
   # Should see /data/generation_logs.json
   ```

2. **Verify Metrics Collection:**
   ```python
   from ai_pipeline.monitoring.metrics import collect_metrics_scheduled
   collect_metrics_scheduled.remote()
   ```

3. **Check Alerts:**
   ```python
   from ai_pipeline.monitoring.alerts import check_alerts_now
   alerts = check_alerts_now.remote()
   ```

4. **View Dashboard:**
   ```python
   from ai_pipeline.monitoring.dashboard import get_dashboard_data
   data = get_dashboard_data.remote(hours=24)
   ```

## Best Practices

1. **Log Immediately** - Don't batch logs, log as soon as generation completes
2. **Include All Fields** - Fill in as many fields as possible for better insights
3. **Handle Errors** - Wrap logging in try/except to not break generation
4. **Use Consistent IDs** - Use same generation_id format across services
5. **Estimate Costs Accurately** - Update cost calculation based on actual GPU usage

## Performance Impact

Logging is lightweight:
- Writes to Modal volume (fast)
- Non-blocking (async-friendly)
- Minimal overhead (~1ms per log)

Safe to add to production without performance concerns.
