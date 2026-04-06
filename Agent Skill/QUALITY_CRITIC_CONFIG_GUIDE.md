# 🎛️ Quality Critic Configuration Guide

**Updated:** April 7, 2026
**Purpose:** Complete `.env.local` configuration reference for Quality Critic

---

## 📋 Quick Reference

All Quality Critic settings are controlled via `.env.local` file. You have **FULL CONTROL** over quality thresholds, revision cycles, and Beast gates.

---

## 🔧 Configuration Variables

### 1. `QUALITY_CRITIC_THRESHOLD`
**What it does:** Minimum overall score (0-10) to APPROVE an image

```bash
QUALITY_CRITIC_THRESHOLD=8.5  # Default: 8.5 (strict)
```

**Logic:**
```python
if overall_score >= 8.5:
    verdict = "APPROVED" ✅
else:
    verdict = "REVISE" 🔧 (generate variants)
```

**Examples:**
```
Score 8.7 → APPROVED ✅
Score 8.2 → REVISE 🔧
Score 7.8 → REVISE 🔧
```

**Tuning Recommendations:**
- `9.0` = Ultra strict (world-class only) — Ultra tier
- `8.5` = Strict (Beast standard) — Premium tier (DEFAULT)
- `8.0` = Medium (good quality) — Standard tier
- `7.5` = Relaxed (acceptable quality) — Testing/shadow mode

---

### 2. `QUALITY_DIMENSION_FLOOR`
**What it does:** Minimum score per dimension (hard floor, any dimension below = auto REVISE)

```bash
QUALITY_DIMENSION_FLOOR=7.0  # Default: 7.0
```

**Logic:**
```python
for dimension in [composition, color, typography, ...]:
    if dimension_score < 7.0:
        verdict = "REVISE"  # Automatic rejection
        weak_dimension = dimension  # Target this for fix
```

**Example:**
```
composition: 9.0 ✅
color_authority: 8.5 ✅
typography: 8.0 ✅
text_legibility: 6.5 ❌ (below 7.0 floor)
overall_score: 8.3 (good!)

Result: REVISE (text_legibility failed floor check)
Critique: "Increase CTA size by 30%, add drop shadow"
```

**Tuning Recommendations:**
- `7.5` = Very strict floor — Ultra tier
- `7.0` = Strict floor — Premium tier (DEFAULT)
- `6.5` = Medium floor — Standard tier
- `6.0` = Relaxed floor — Testing/shadow mode

---

### 3. `QUALITY_REVISION_MAX_CYCLES`
**What it does:** Maximum revision attempts before giving up (ESCALATE to human)

```bash
QUALITY_REVISION_MAX_CYCLES=3  # Default: 3
```

**Logic:**
```python
revision_cycle = 0

while revision_cycle <= 3:
    if verdict == "APPROVED":
        break  ✅
    elif revision_cycle >= 3:
        verdict = "ESCALATE"  🚨 (give up)
        break
    else:
        revision_cycle += 1
        generate_variant()  # Try again
```

**Example:**
```
Cycle 1: Score 7.5 → REVISE → Gen variant 1
Cycle 2: Score 8.0 → REVISE → Gen variant 2
Cycle 3: Score 8.3 → REVISE → Gen variant 3
Cycle 4: Max reached → ESCALATE 🚨 (human review)
```

**Tuning Recommendations:**
- `5` = Very patient (quality critical, slower) — If quality >> speed
- `3` = Balanced (default) — Premium/Ultra tier (DEFAULT)
- `2` = Fast (good enough, quicker) — Premium tier
- `1` = Single retry only — Standard tier
- `0` = No revisions — Testing only

**Cost Impact:**
- Max cycles = 3 → Average 1.25 generations per request
- Max cycles = 1 → Average 1.15 generations per request
- Max cycles = 5 → Average 1.40 generations per request

---

### 4. `QUALITY_BEAST_GATES_MIN`
**What it does:** Minimum Beast gates (out of 10) that must PASS

```bash
QUALITY_BEAST_GATES_MIN=9  # Default: 9 (9/10 must pass)
```

**Logic:**
```python
beast_gates_passed = 9  # 9 out of 10 passed

if beast_gates_passed < 9:
    verdict = "ESCALATE"  🚨 (fundamental issues)
else:
    proceed_with_dimension_scoring()
```

**Example:**
```
10 Beast Gates:
  ✅ Stranger Test: Pass
  ✅ Scroll-Stop Test: Pass
  ✅ Remove-Color Test: Pass
  ❌ 10% Size Test: FAIL
  ✅ Tomorrow Test: Pass
  ✅ Brand-Remove Test: Pass
  ✅ Emotion Test: Pass
  ✅ Competitor Test: Pass
  ✅ Context Test: Pass
  ✅ Memory Test: Pass

Gates passed: 9/10 ✅ (meets min 9)
  ↓
Continue with dimension scoring...
```

**Tuning Recommendations:**
- `10` = ALL gates must pass (maximum strict) — Ultra tier
- `9` = 9/10 gates must pass (very strict) — Premium tier (DEFAULT)
- `8` = 8/10 gates must pass (medium) — Standard tier
- `7` = 7/10 gates must pass (relaxed) — Testing/shadow mode

**Warning:** Setting this < 7 may allow poor-quality outputs!

---

## 🎯 Tier-Specific Configuration (Recommended Setup)

### Current `.env.local` Configuration:

```bash
# ─── Quality Critic Configuration (Sprint 1: Beast Mode) ───

# Global defaults (used if tier-specific not set)
QUALITY_CRITIC_THRESHOLD=8.5
QUALITY_DIMENSION_FLOOR=7.0
QUALITY_REVISION_MAX_CYCLES=3
QUALITY_BEAST_GATES_MIN=9

# Tier-specific overrides (optional)

# STANDARD tier (relaxed for speed)
QUALITY_CRITIC_THRESHOLD_STANDARD=8.0
QUALITY_DIMENSION_FLOOR_STANDARD=6.5
QUALITY_REVISION_MAX_CYCLES_STANDARD=1
QUALITY_BEAST_GATES_MIN_STANDARD=8

# PREMIUM tier (balanced quality)
QUALITY_CRITIC_THRESHOLD_PREMIUM=8.5
QUALITY_DIMENSION_FLOOR_PREMIUM=7.0
QUALITY_REVISION_MAX_CYCLES_PREMIUM=2
QUALITY_BEAST_GATES_MIN_PREMIUM=9

# ULTRA tier (maximum strict)
QUALITY_CRITIC_THRESHOLD_ULTRA=9.0
QUALITY_DIMENSION_FLOOR_ULTRA=7.5
QUALITY_REVISION_MAX_CYCLES_ULTRA=3
QUALITY_BEAST_GATES_MIN_ULTRA=10
```

---

## 📊 Tier Comparison Table

| Setting | FAST ⚡ | STANDARD 🟢 | PREMIUM 🟡 | ULTRA 🔴 |
|---------|---------|------------|-----------|----------|
| **Quality Check** | ❌ NO | ✅ YES | ✅ YES | ✅ YES |
| **Threshold** | N/A | 8.0 | 8.5 | 9.0 |
| **Dimension Floor** | N/A | 6.5 | 7.0 | 7.5 |
| **Max Revision Cycles** | 0 | 1 | 2 | 3 |
| **Beast Gates Min** | N/A | 8/10 | 9/10 | 10/10 |
| **Avg Time** | ~5s | ~13-26s | ~20-40s | ~35-70s |
| **Quality Output** | 6.5-7.5/10 | 7.5-8.5/10 | 8.5-9.0/10 | 9.0-9.5/10 |
| **Use Case** | Speed first | Good quality | World-class | Agency-level |

---

## 🔄 How Tier-Specific Config Works

### Code Logic:
```python
# In quality_critic.py
class QualityCritic:
    def __init__(self, tier="premium"):
        self.tier = tier
        self.config = _get_tier_config(tier)
        # self.config = {
        #     "threshold": 8.5,
        #     "dimension_floor": 7.0,
        #     "max_cycles": 2,
        #     "beast_gates_min": 9
        # }

def _get_tier_config(tier):
    """Reads .env for tier-specific overrides, falls back to global."""
    tier_upper = tier.upper()  # "premium" → "PREMIUM"

    return {
        "threshold": float(os.getenv(
            f"QUALITY_CRITIC_THRESHOLD_{tier_upper}",  # e.g., QUALITY_CRITIC_THRESHOLD_PREMIUM
            QUALITY_CRITIC_THRESHOLD  # Fallback to global default
        )),
        "dimension_floor": float(os.getenv(
            f"QUALITY_DIMENSION_FLOOR_{tier_upper}",
            QUALITY_DIMENSION_FLOOR
        )),
        "max_cycles": int(os.getenv(
            f"QUALITY_REVISION_MAX_CYCLES_{tier_upper}",
            QUALITY_REVISION_MAX_CYCLES
        )),
        "beast_gates_min": int(os.getenv(
            f"QUALITY_BEAST_GATES_MIN_{tier_upper}",
            QUALITY_BEAST_GATES_MIN
        )),
    }
```

### In generate_stream.py:
```python
# Map quality tier to critic tier
critic_tier = "premium" if quality == "quality" else quality
# quality="quality" → tier="premium" (STANDARD tier uses PREMIUM config)
# quality="premium" → tier="premium"
# quality="ultra" → tier="ultra"

critic = QualityCritic(tier=critic_tier)
```

---

## 🎛️ Tuning Examples

### Example 1: Relaxed Standard Tier (Faster)
**Goal:** Standard tier should be fast and forgiving

```bash
QUALITY_CRITIC_THRESHOLD_STANDARD=7.5  # Lower threshold
QUALITY_DIMENSION_FLOOR_STANDARD=6.0   # Lower floor
QUALITY_REVISION_MAX_CYCLES_STANDARD=1  # Single retry only
QUALITY_BEAST_GATES_MIN_STANDARD=7     # 7/10 gates
```

**Result:**
- Faster (~15-20s avg)
- More forgiving (lower quality bar)
- Good for testing/prototyping

---

### Example 2: Strict Premium Tier (Agency-Level)
**Goal:** Premium tier should deliver world-class quality

```bash
QUALITY_CRITIC_THRESHOLD_PREMIUM=9.0   # Very high threshold
QUALITY_DIMENSION_FLOOR_PREMIUM=7.5    # High floor
QUALITY_REVISION_MAX_CYCLES_PREMIUM=3  # Three retries
QUALITY_BEAST_GATES_MIN_PREMIUM=10     # ALL gates must pass
```

**Result:**
- Slower (~60-90s avg)
- Highest quality (9.0+ avg)
- Best for client-facing work

---

### Example 3: Disable Quality Critic (Testing)
**Goal:** Turn off quality checks temporarily

```bash
# In generate_stream.py, modify this line:
_run_quality_gate = (
    quality != "fast"
    and quality != "quality"  # Add this to skip STANDARD tier
    and quality != "premium"  # Add this to skip PREMIUM tier
    and bool(creative_bible.get("emotional_territory"))
)
```

**OR set very low thresholds:**
```bash
QUALITY_CRITIC_THRESHOLD=0.0  # Always approve
QUALITY_DIMENSION_FLOOR=0.0   # No floor
QUALITY_REVISION_MAX_CYCLES=0  # No revisions
```

---

## 🚀 Rollout Strategy (Tuning Over Time)

### Week 1: Shadow Mode (Validation)
```bash
# Log scores but don't block outputs
QUALITY_CRITIC_THRESHOLD=7.5  # Easy to pass
QUALITY_DIMENSION_FLOOR=6.0   # Soft floor
QUALITY_REVISION_MAX_CYCLES=1  # Single retry
QUALITY_BEAST_GATES_MIN=7     # 7/10 gates
```
**Goal:** Validate scoring accuracy, no user friction

---

### Week 2: Soft Enforcement (Testing)
```bash
# Block some bad outputs, allow most
QUALITY_CRITIC_THRESHOLD=8.0  # Medium bar
QUALITY_DIMENSION_FLOOR=6.5   # Medium floor
QUALITY_REVISION_MAX_CYCLES=1  # Single retry
QUALITY_BEAST_GATES_MIN=8     # 8/10 gates
```
**Goal:** Test revision loop, measure quality improvement

---

### Week 3: Full Enforcement (Production)
```bash
# Enforce Beast Standard fully
QUALITY_CRITIC_THRESHOLD=8.5  # Strict
QUALITY_DIMENSION_FLOOR=7.0   # Hard floor
QUALITY_REVISION_MAX_CYCLES=2  # Two retries
QUALITY_BEAST_GATES_MIN=9     # 9/10 gates
```
**Goal:** World-class quality enforced

---

## 📊 Monitoring Queries

### Track Quality Over Time:
```sql
SELECT
    DATE(created_at) as date,
    tier,
    AVG(overall_score) as avg_score,
    AVG(beast_gates_passed) as avg_gates,
    AVG(revision_cycles) as avg_revisions,
    SUM(CASE WHEN verdict='APPROVED' THEN 1 ELSE 0 END) / COUNT(*) as approval_rate
FROM generations
WHERE quality_score IS NOT NULL
GROUP BY DATE(created_at), tier
ORDER BY date DESC, tier;
```

### Find Optimal Thresholds:
```sql
-- What threshold gives 85% approval rate?
SELECT
    FLOOR(overall_score * 10) / 10 as score_bucket,
    COUNT(*) as images,
    SUM(CASE WHEN revision_cycles = 0 THEN 1 ELSE 0 END) / COUNT(*) as first_pass_rate
FROM generations
WHERE quality_score IS NOT NULL
GROUP BY score_bucket
ORDER BY score_bucket DESC;
```

---

## 🎯 TL;DR (Quick Summary)

**Where to configure:** `.env.local` file (4 main variables)

**What you control:**
1. `QUALITY_CRITIC_THRESHOLD` — Min score to approve (8.5 default)
2. `QUALITY_DIMENSION_FLOOR` — Per-dimension floor (7.0 default)
3. `QUALITY_REVISION_MAX_CYCLES` — Max retry attempts (3 default)
4. `QUALITY_BEAST_GATES_MIN` — Min gates to pass (9/10 default)

**Tier-specific:** Add `_STANDARD`, `_PREMIUM`, or `_ULTRA` suffix to variable names

**Example:**
```bash
QUALITY_CRITIC_THRESHOLD=8.5            # Global default
QUALITY_CRITIC_THRESHOLD_STANDARD=8.0   # Standard tier override
QUALITY_CRITIC_THRESHOLD_ULTRA=9.0      # Ultra tier override
```

**Restart needed?** ❌ NO — `.env` is read at runtime, just restart API server

---

**Full control hai bhai! Tune karo jaise chahiye! 🎛️**
