# Dual Pipeline Safety System - Usage Examples

## Quick Start

```python
from app.services.safety import run_pre_check, run_post_check

# ===== STAGE 1: PRE-GENERATION =====
pre_result = await run_pre_check(
    user_id="user_123",
    prompt="professional headshot",
    mode="REALISM",
    identity_id="identity_456"  # Optional
)

if not pre_result.allowed:
    return {"error": pre_result.reason, "violations": pre_result.violations}

# ===== GENERATE IMAGE =====
image_path = await generate_image(pre_result.modified_prompt or prompt)

# ===== STAGE 2: POST-GENERATION =====
post_result = await run_post_check(
    image_path=image_path,
    user_id="user_123",
    generation_id="gen_789",
    mode="REALISM"
)

if not post_result.safe:
    if post_result.action == "BLOCK":
        return {"error": "Image blocked", "violations": post_result.violations}
    elif post_result.action == "QUARANTINE":
        return {"status": "quarantined", "requires_review": True}

# ===== SUCCESS =====
return {"success": True, "image_path": image_path}
```

## Complete Integration Example

```python
from app.services.safety import DualPipelineSafety
from app.core.database import get_db

pipeline = DualPipelineSafety()

async def generate_with_safety(
    user_id: str,
    prompt: str,
    mode: str,
    identity_id: Optional[str] = None
):
    async with get_db() as db:
        # Pre-check
        pre_check = await pipeline.pre_generation_check(
            user_id=user_id,
            prompt=prompt,
            mode=mode,
            identity_id=identity_id,
            db_session=db
        )
        
        if not pre_check.allowed:
            return {
                "success": False,
                "error": pre_check.reason,
                "violations": pre_check.violations,
                "suggested_prompt": pre_check.modified_prompt
            }
        
        # Generate image
        image_path = await generate_image(
            prompt=pre_check.modified_prompt or prompt,
            mode=mode
        )
        
        generation_id = f"gen_{uuid.uuid4()}"
        
        # Post-check
        post_check = await pipeline.post_generation_check(
            image_path=image_path,
            user_id=user_id,
            generation_id=generation_id,
            mode=mode,
            db_session=db
        )
        
        if not post_check.safe:
            return {
                "success": False,
                "error": f"Image {post_check.action.lower()}",
                "violations": post_check.violations,
                "strike_added": post_check.user_strike_added
            }
        
        return {
            "success": True,
            "image_path": image_path,
            "generation_id": generation_id
        }
```

## Statistics

```python
from app.services.safety import dual_pipeline

stats = dual_pipeline.get_statistics()
print(f"Pre-gen checks: {stats['pre_gen_checks']}")
print(f"Block rate: {stats.get('pre_gen_block_rate', 0):.2%}")
```
