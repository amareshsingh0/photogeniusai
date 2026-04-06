# 🎯 Sequential Multi-Variant Generation Strategy

**Updated:** April 7, 2026
**Philosophy:** Generate on-demand, not in advance. Pick best, show only best to user.

---

## 💡 The Idea

Instead of blindly retrying when quality is low, **generate multiple variants sequentially** and pick the best one.

### OLD Approach (Blind Retry):
```
Gen 1 → Check → Score 7.5 → REVISE → Gen 2 → Check → Score 8.0 → APPROVED
(No intelligence, just re-roll the dice)
```

### NEW Approach (Sequential Smart Variants):
```
Gen 1 → Check → Score 7.5 → REVISE
  ↓
Gen 2 (with fix) → Check → Score 8.6 → APPROVED ✅
  ↓
User sees only the BEST one (8.6/10)
```

---

## 🎯 How It Works (Step-by-Step)

### Step 1: First Generation
```python
User: "Create luxury watch ad for Instagram"
  ↓
Generate image 1 (Flux Dev, ~15s)
  ↓
Quality Critic checks (5s)
  ↓
Score: 7.8/10
Weak dimension: text_legibility = 6.5
Verdict: REVISE
```

### Step 2: Sequential Variant Generation (IF REVISE)
```python
Revision triggered:
  Critique: "Increase CTA size, improve contrast"
  ↓
Generate variant 1 with fix (~15s)
  Prompt: "luxury watch ad — IMPROVE: Increase CTA size, improve contrast"
  ↓
Quick quality check (5s)
  Score: 8.2/10
  Verdict: REVISE (still not 8.5+)
  ↓
Is variant 1 APPROVED? NO
Do we have more attempts? YES (max 2 per cycle)
  ↓
Generate variant 2 with alternative approach (~15s)
  Prompt: "luxury watch ad — IMPROVE: Increase CTA size, alternative composition, fresh perspective"
  ↓
Quick quality check (5s)
  Score: 8.7/10
  Verdict: APPROVED ✅
  ↓
STOP! Variant 2 approved, no need for more
```

### Step 3: User Sees Best
```python
Variant 1: 8.2/10 ❌ (not shown)
Variant 2: 8.7/10 ✅ (delivered to user)

User sees: Single high-quality image (8.7/10)
```

---

## ⚙️ Configuration (Tier-Wise)

### FAST Tier ⚡
```python
Variants: 0 (no quality check at all)
Strategy: Single shot, deliver immediately
Time: ~3-5s
```

### STANDARD Tier 🟢
```python
Variants: 2 (sequential, pick best)
Threshold: 8.0/10
Strategy:
  - Gen 1 → Check
  - If REVISE: Gen 2 → Check
  - Pick best OR first APPROVED
Max time: ~40s (15+5+15+5)
```

### PREMIUM Tier 🟡
```python
Variants: 2 (sequential, pick best)
Threshold: 8.5/10 (strict)
Strategy:
  - Gen 1 → Check
  - If REVISE: Gen 2 → Check
  - Pick best OR first APPROVED
Max time: ~40s (15+5+15+5)
```

### ULTRA Tier 🔴
```python
Variants: 2 (sequential, pick best)
Threshold: 9.0/10 (maximum strict)
Strategy:
  - Gen 1 → Check
  - If REVISE: Gen 2 → Check
  - Pick best OR first APPROVED
Max time: ~70s (30+5+30+5)
```

---

## 📊 Sequential Logic (Code Flow)

```python
def sequential_variant_generation(prompt, max_variants=2):
    best_score = 0.0
    best_url = None

    for i in range(max_variants):
        # Build variant prompt
        if i == 0:
            variant_prompt = f"{prompt} — IMPROVE: {critique}"
        else:
            variant_prompt = f"{prompt} — IMPROVE: {critique}, alternative composition"

        # Generate variant
        image_url = generate(variant_prompt)

        # Quick quality check
        score, verdict = quality_critic.critique(image_url)

        # Track best
        if score > best_score:
            best_score = score
            best_url = image_url

        # Stop if APPROVED
        if verdict == "APPROVED":
            return image_url, score  # Use this one!

    # No APPROVED variant, use best one
    return best_url, best_score
```

---

## 🔄 Example Scenarios

### Scenario 1: First Variant Approved (70% cases)
```
Gen 1: (~15s) → Score 8.7 → APPROVED ✅
  ↓
STOP! No need for variant 2
  ↓
User sees: Gen 1 (8.7/10)
Total time: ~20s (15 gen + 5 check)
```

### Scenario 2: Second Variant Better (25% cases)
```
Gen 1: (~15s) → Score 8.2 → REVISE
  ↓
Gen 2: (~15s) → Score 8.8 → APPROVED ✅
  ↓
User sees: Gen 2 (8.8/10, the better one)
Total time: ~40s (15+5+15+5)
```

### Scenario 3: No APPROVED, Pick Best (5% cases)
```
Gen 1: (~15s) → Score 7.8 → REVISE
  ↓
Gen 2: (~15s) → Score 8.3 → REVISE (still not 8.5+)
  ↓
Max 2 variants reached, pick best
  ↓
User sees: Gen 2 (8.3/10, the better of two)
Total time: ~40s
```

---

## 🎯 Why Sequential (Not Parallel)?

### ❌ Parallel Approach (Wasteful):
```
Gen 1 + Gen 2 at SAME TIME (30s both running)
  ↓
Check both (5s each)
  ↓
Pick best
  ↓
Problem: Waste Gen 2 compute if Gen 1 is already APPROVED!
Cost: 2× generation cost every time
```

### ✅ Sequential Approach (Smart):
```
Gen 1 (30s) → Check (5s) → APPROVED?
  ↓
YES → STOP (save Gen 2 cost!)
NO → Gen 2 (30s) → Check (5s)
  ↓
Savings: 50-70% of cases need only 1 generation
Cost: 1.3× average (not 2×)
```

**Cost Efficiency:**
- 70% cases: 1 generation only
- 25% cases: 2 generations
- 5% cases: 2 generations (no improvement)
- **Average: 1.25 generations per request** (vs 2.0 in parallel)

---

## 📈 Expected Improvements

### Before Sequential Variants:
```
Quality: 7.2/10 avg
Revision success rate: 60% (blind retry)
User satisfaction: "Sometimes good, sometimes meh"
```

### After Sequential Variants:
```
Quality: 8.5+/10 avg
Revision success rate: 85% (smart variants)
User satisfaction: "Consistently high quality"
```

### Time Comparison:

| Scenario | Old (Serial Retry) | New (Sequential Variants) |
|----------|-------------------|--------------------------|
| 70% (first good) | ~20s (1 gen) | ~20s (1 gen) |
| 25% (needs retry) | ~40s (retry blind) | ~40s (2 variants, pick best) |
| 5% (multiple retries) | ~60-80s (3 blind retries) | ~40s (2 variants max, best picked) |
| **Average** | ~30s | ~26s (13% faster) |

---

## 🎨 User Experience

### What User Sees:

**Progress Messages:**
```
1. "Generating luxury watch ad... (15s)"
2. "Quality review in progress... (5s)"
3. "Score: 8.2/10 — Generating improved variant..."
4. "Variant 2 generating... (15s)"
5. "Quality review: Variant 2... (5s)"
6. "✅ Best result selected! Score: 8.8/10"
```

**Final Output:**
```
User sees: Single high-quality image (8.8/10)
Quality badge: "Grade: A (8.8/10)"
Variants generated: 2 (invisible to user)
Variant shown: Best one
```

**User never sees:**
- The rejected variant (8.2/10)
- The internal quality scores
- The revision loop complexity

**User only sees:**
- The best possible output
- Final quality grade
- Smooth progress updates

---

## 🔧 Configuration (.env)

```bash
# Tier-wise variant counts
STANDARD_MAX_VARIANTS=2
PREMIUM_MAX_VARIANTS=2
ULTRA_MAX_VARIANTS=2

# Quality thresholds (when to generate variants)
QUALITY_CRITIC_THRESHOLD=8.5
QUALITY_DIMENSION_FLOOR=7.0

# Variant generation strategy
VARIANT_GENERATION_MODE=sequential  # sequential (not parallel)
VARIANT_PICK_STRATEGY=first_approved_or_best  # stop early if good enough
```

---

## 🚀 Rollout Strategy

### Week 1: Shadow Mode
- Generate 2 variants but log only (don't pick best)
- Compare: Does variant 2 actually improve quality?
- **Goal:** Validate that 2nd variant is worth the compute

### Week 2: PREMIUM Tier Only
- Enable sequential variants for PREMIUM tier
- Max 2 variants per revision cycle
- **Goal:** Test user satisfaction improvement

### Week 3: STANDARD + PREMIUM + ULTRA
- Enable for all non-FAST tiers
- Monitor: Average variants per request, quality improvement
- **Goal:** Full production rollout

---

## 📊 Success Metrics

### Primary Metrics:
```sql
-- Track variant usage
SELECT
    tier,
    AVG(variants_attempted) as avg_variants,
    AVG(CASE WHEN variant_selected = 0 THEN 1 ELSE 0 END) as first_variant_win_rate,
    AVG(overall_score) as avg_quality
FROM generations
WHERE variants_attempted > 0
GROUP BY tier;
```

### Target KPIs (30 days):
- First variant win rate: **70%+** (most images good on first try)
- Second variant improvement: **+0.5 avg score** (when generated)
- Average variants per request: **1.25** (cost efficient)
- Quality score avg: **8.5+/10** (world-class)

---

## 🎯 TL;DR (Quick Summary)

**What:** Generate up to 2 variants **sequentially** (not parallel), pick best

**When:** STANDARD/PREMIUM/ULTRA tiers when quality < 8.5

**How:**
1. Gen 1 → Check → APPROVED? → STOP (70% cases)
2. Gen 1 → Check → REVISE? → Gen 2 → Check → Pick best (30% cases)

**Why:**
- **Smarter** than blind retry (alternative approaches)
- **Cheaper** than parallel (generate only if needed)
- **Faster** than multiple revision cycles (max 2 variants per cycle)

**Result:**
- Quality: 7.2 → 8.5+ avg (+18%)
- User sees: Only the BEST variant (never the rejects)
- Cost: 1.25× avg (not 2×, because stop early if good)

---

**Sequential = Smart. User sees best only. Beast Mode ACTIVATED! 🦁**
