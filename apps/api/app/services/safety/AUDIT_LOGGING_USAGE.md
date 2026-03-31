# Safety Audit Logging - Usage Guide

## Overview

The Safety Audit Logger provides comprehensive logging of all safety checks with:
- **180-day retention policy**
- **Query capabilities** (by user, generation, violation type)
- **Analytics aggregation**
- **Export functionality** (JSON, CSV)
- **Privacy compliance** (prompt truncation, IP masking)
- **Performance optimization** (async operations, file redundancy)

## Quick Start

### Basic Logging

```python
from app.services.safety.audit_logger import audit_logger, AuditEventType

# Log a safety event
await audit_logger.log_event(
    event_type=AuditEventType.PRE_GEN_BLOCK,
    user_id="user_123",
    generation_id="gen_456",
    stage="PRE_GENERATION",
    action="BLOCK",
    violations=[{"type": "CELEBRITY", "severity": "HIGH"}],
    prompt="unsafe prompt text",
    ip_address="192.168.1.1",
    db_session=db_session
)
```

## Integration with Dual Pipeline

### Option 1: Manual Integration

```python
from app.services.safety import dual_pipeline, audit_logger, AuditEventType, SafetyStage
from app.core.database import get_db

async def generate_with_audit(user_id: str, prompt: str, mode: str, identity_id: str):
    async with get_db() as db:
        # Pre-generation check
        pre_result = await dual_pipeline.pre_generation_check(
            user_id=user_id,
            prompt=prompt,
            mode=mode,
            identity_id=identity_id,
            db_session=db
        )
        
        # Log pre-generation result
        await audit_logger.log_event(
            event_type=AuditEventType.PRE_GEN_BLOCK if not pre_result.allowed else AuditEventType.PRE_GEN_ALLOW,
            user_id=user_id,
            stage=SafetyStage.PRE_GENERATION.value,
            action="BLOCK" if not pre_result.allowed else "ALLOW",
            violations=pre_result.violations if not pre_result.allowed else None,
            prompt=prompt,
            metadata=pre_result.metadata,
            db_session=db
        )
        
        if not pre_result.allowed:
            return {"error": pre_result.reason}
        
        # Generate image...
        image_path = "/path/to/generated.png"
        generation_id = "gen_789"
        
        # Post-generation check
        post_result = await dual_pipeline.post_generation_check(
            image_path=image_path,
            user_id=user_id,
            generation_id=generation_id,
            mode=mode,
            db_session=db
        )
        
        # Log post-generation result
        event_type_map = {
            "ALLOW": AuditEventType.POST_GEN_ALLOW,
            "BLOCK": AuditEventType.POST_GEN_BLOCK,
            "QUARANTINE": AuditEventType.POST_GEN_QUARANTINE,
        }
        
        await audit_logger.log_event(
            event_type=event_type_map.get(post_result.action, AuditEventType.POST_GEN_BLOCK),
            user_id=user_id,
            generation_id=generation_id,
            stage=SafetyStage.POST_GENERATION.value,
            action=post_result.action,
            violations=post_result.violations if not post_result.safe else None,
            scores={"nsfw_score": post_result.metadata.get("nsfw_score")} if "nsfw_score" in post_result.metadata else None,
            image_url=image_path,
            metadata=post_result.metadata,
            db_session=db
        )
        
        return {"success": post_result.safe, "action": post_result.action}
```

### Option 2: Automatic Integration (Recommended)

Modify `dual_pipeline.py` to automatically log events:

```python
# In pre_generation_check method, after each return:
from .audit_logger import audit_logger, AuditEventType

# After blocking/allowing, add:
await audit_logger.log_event(
    event_type=AuditEventType.PRE_GEN_BLOCK if not result.allowed else AuditEventType.PRE_GEN_ALLOW,
    user_id=user_id,
    stage=SafetyStage.PRE_GENERATION.value,
    action="BLOCK" if not result.allowed else "ALLOW",
    violations=result.violations,
    prompt=prompt,
    metadata=result.metadata,
    db_session=db_session
)
```

## Querying Audit Logs

### Query by User

```python
from datetime import datetime, timedelta

# Get user's last 100 safety events
logs = await audit_logger.query_by_user(
    user_id="user_123",
    limit=100,
    db_session=db_session
)

# Get user's violations in last 30 days
start_date = datetime.utcnow() - timedelta(days=30)
logs = await audit_logger.query_by_user(
    user_id="user_123",
    start_date=start_date,
    event_types=[AuditEventType.PRE_GEN_BLOCK, AuditEventType.POST_GEN_BLOCK],
    db_session=db_session
)
```

### Query by Generation

```python
# Get all safety checks for a generation
logs = await audit_logger.query_by_generation(
    generation_id="gen_789",
    db_session=db_session
)
```

### Query by Violation Type

```python
# Get all NSFW violations
nsfw_logs = await audit_logger.query_violations(
    violation_type="NSFW",
    limit=100,
    db_session=db_session
)

# Get all celebrity violations in last week
start_date = datetime.utcnow() - timedelta(days=7)
celebrity_logs = await audit_logger.query_violations(
    violation_type="CELEBRITY",
    start_date=start_date,
    db_session=db_session
)
```

## Analytics

### System-Wide Analytics

```python
from datetime import datetime, timedelta

start_date = datetime.utcnow() - timedelta(days=30)
end_date = datetime.utcnow()

analytics = await audit_logger.get_analytics(
    start_date=start_date,
    end_date=end_date,
    db_session=db_session
)

print(f"Total checks: {analytics['total_checks']}")
print(f"Blocks: {analytics['blocks']}")
print(f"Quarantines: {analytics['quarantines']}")
print(f"Average NSFW score: {analytics['nsfw_average_score']}")
```

### User Analytics

```python
user_analytics = await audit_logger.get_user_analytics(
    user_id="user_123",
    db_session=db_session
)

print(f"User violations: {user_analytics['violations']}")
print(f"User strikes: {user_analytics['strikes']}")
print(f"Last violation: {user_analytics['last_violation']}")
```

## Export

### Export to JSON

```python
from datetime import datetime, timedelta

start_date = datetime.utcnow() - timedelta(days=7)
json_data = await audit_logger.export_logs(
    start_date=start_date,
    format="json",
    db_session=db_session
)

# Save to file
with open("safety_logs.json", "wb") as f:
    f.write(json_data)
```

### Export to CSV

```python
csv_data = await audit_logger.export_logs(
    user_id="user_123",  # Optional filter
    format="csv",
    db_session=db_session
)

# Save to file
with open("safety_logs.csv", "wb") as f:
    f.write(csv_data)
```

## Cleanup

### Manual Cleanup

```python
# Delete logs older than retention period (180 days)
deleted_count = await audit_logger.cleanup_expired_logs(
    db_session=db_session
)

print(f"Deleted {deleted_count} expired logs")
```

### Scheduled Cleanup

Set up a cron job or scheduled task:

```python
# In your scheduler (e.g., FastAPI background task)
async def scheduled_cleanup():
    while True:
        await asyncio.sleep(86400)  # Run daily
        await audit_logger.cleanup_expired_logs(db_session=db_session)
```

## Event Types

Available event types:

- **Pre-generation**: `PRE_GEN_BLOCK`, `PRE_GEN_ALLOW`, `PROMPT_VIOLATION`, `RATE_LIMIT`
- **Post-generation**: `POST_GEN_BLOCK`, `POST_GEN_QUARANTINE`, `POST_GEN_ALLOW`, `NSFW_DETECTED`, `UNDERAGE_DETECTED`
- **User actions**: `STRIKE_ADDED`, `STRIKE_REMOVED`, `USER_APPEAL`, `USER_BANNED`
- **System**: `SYSTEM_ERROR`

## Privacy & Compliance

The audit logger automatically:
- **Truncates prompts** to 500 characters
- **Truncates user agents** to 500 characters
- **Sets expiration dates** (180 days)
- **Allows IP masking** (set `ip_address=None` if needed)

## File Logging

Logs are also written to files in `logs/safety/` directory:
- Daily files: `safety_YYYY-MM-DD.log`
- JSON format, one entry per line
- Automatic directory creation

## Statistics

```python
stats = audit_logger.get_statistics()
print(f"Total logs: {stats['total_logs']}")
print(f"Blocks: {stats['blocks']}")
print(f"Quarantines: {stats['quarantines']}")
print(f"Strikes: {stats['strikes']}")
```

## Database Schema (TODO)

When implementing database storage, create a table:

```sql
CREATE TABLE safety_audit_logs (
    id SERIAL PRIMARY KEY,
    event_type VARCHAR(50) NOT NULL,
    user_id VARCHAR(255),
    generation_id VARCHAR(255),
    stage VARCHAR(50),
    action VARCHAR(50),
    violations JSONB,
    scores JSONB,
    prompt TEXT,
    image_url TEXT,
    ip_address VARCHAR(45),
    user_agent TEXT,
    metadata JSONB,
    timestamp TIMESTAMP NOT NULL,
    expires_at TIMESTAMP NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_safety_audit_user ON safety_audit_logs(user_id);
CREATE INDEX idx_safety_audit_generation ON safety_audit_logs(generation_id);
CREATE INDEX idx_safety_audit_timestamp ON safety_audit_logs(timestamp);
CREATE INDEX idx_safety_audit_expires ON safety_audit_logs(expires_at);
CREATE INDEX idx_safety_audit_event_type ON safety_audit_logs(event_type);
CREATE INDEX idx_safety_audit_violations ON safety_audit_logs USING GIN(violations);
```

## Performance Tips

1. **Use async operations** - All methods are async
2. **Batch queries** - Use date ranges to limit results
3. **Index database** - Create indexes on frequently queried fields
4. **File logging is fast** - File writes are synchronous but lightweight
5. **Optional DB session** - If `db_session=None`, only file logging occurs

## Next Steps

1. **Create database model** in `app/models/safety.py`
2. **Implement database queries** (replace TODO comments)
3. **Add API endpoints** for querying/exporting logs
4. **Set up scheduled cleanup** task
5. **Integrate with dual_pipeline** for automatic logging
