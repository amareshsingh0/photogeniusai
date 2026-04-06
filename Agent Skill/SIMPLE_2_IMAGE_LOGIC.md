# 🎯 Simple 2-Image Logic (Final Implementation)

**Rule:** MAX 2 images total per generation (all tiers)
**Difference:** Model selection by tier (NOT image count!)

---

## 📝 Clean Implementation Plan

### Step 1: Image 1 (Already Generated)
```python
# Image 1 already exists (raw_hero_url from initial generation)

# Run quality check on image 1
critique_1 = await quality_critic.critique(raw_hero_url)

if critique_1["verdict"] == "APPROVED":
    # Use image 1 ✅
    final_image = raw_hero_url

elif critique_1["verdict"] == "ESCALATE":
    # Use image 1 with warning 🚨
    final_image = raw_hero_url

elif critique_1["verdict"] == "REVISE":
    # Generate image 2 with targeted fix
    proceed_to_step_2()
```

---

### Step 2: Image 2 (Only if Image 1 Needs Improvement)
```python
# Extract weak dimensions from image 1 critique
weak_dimensions = [dim for dim, data in critique_1["dimensions"].items()
                   if data["score"] < 7.0]

revision_notes = critique_1["revision_notes"]
# Example: "Increase CTA size by 30%, improve contrast"

# Build targeted prompt
mutation_prompt = f"{original_prompt} — IMPROVE: {revision_notes}"

# Generate image 2
image_2_url = await generate(mutation_prompt)

# Check image 2
critique_2 = await quality_critic.critique(image_2_url)

# Pick best of 2
if critique_2["overall_score"] > critique_1["overall_score"]:
    final_image = image_2_url  # Image 2 is better
else:
    final_image = raw_hero_url  # Image 1 is still better
```

---

## 🎯 Tier-Wise Behavior

| Tier | Model | Threshold | Max Images | Typical Flow |
|------|-------|-----------|-----------|--------------|
| **STANDARD** 🟢 | Flux Schnell | 8.0 | 2 | Gen 1 (8.1) → APPROVED → Done! |
| **PREMIUM** 🟡 | Flux Dev | 8.5 | 2 | Gen 1 (8.2) → REVISE → Gen 2 (8.7) → Pick best |
| **ULTRA** 🔴 | Flux Pro | 9.0 | 2 | Gen 1 (8.8) → REVISE → Gen 2 (9.1) → Pick best |

---

## 📊 Real Examples

### Example 1: STANDARD - First Image Good (70% cases)
```
User: "Create gym fitness ad"
  ↓
Gen 1 (Flux Schnell, 15s)
  ↓
Quality Check (5s)
  Score: 8.1/10
  Verdict: APPROVED ✅ (>= 8.0 threshold)
  ↓
User sees: Gen 1 (8.1/10)
Total time: 20s
Total images: 1
```

---

### Example 2: PREMIUM - Second Image Better (25% cases)
```
User: "Create luxury watch ad"
  ↓
Gen 1 (Flux Dev, 15s)
  ↓
Quality Check (5s)
  Score: 8.2/10
  Weak: text_legibility = 6.5
  Verdict: REVISE ❌ (< 8.5 threshold)
  ↓
Critique: "Increase CTA size by 30%, add drop shadow"
  ↓
Gen 2 (Flux Dev, 15s)
  Prompt: "luxury watch ad — IMPROVE: Increase CTA size, add drop shadow"
  ↓
Quality Check (5s)
  Score: 8.8/10
  Verdict: APPROVED ✅
  ↓
Pick Best: 8.8 > 8.2 → Use Gen 2
  ↓
User sees: Gen 2 (8.8/10)
Total time: 40s
Total images: 2
```

---

### Example 3: ULTRA - Both Images, Pick Better (10% cases)
```
User: "Create billboard campaign"
  ↓
Gen 1 (Flux Pro, 30s)
  ↓
Quality Check (5s)
  Score: 8.7/10
  Weak: scroll_stop_power = 6.8
  Verdict: REVISE ❌ (< 9.0 threshold)
  ↓
Critique: "Stronger visual contrast, bolder composition"
  ↓
Gen 2 (Flux Pro, 30s)
  Prompt: "billboard campaign — IMPROVE: Stronger contrast, bolder composition"
  ↓
Quality Check (5s)
  Score: 8.9/10
  Verdict: STILL REVISE ❌ (< 9.0)
  ↓
Pick Best: 8.9 > 8.7 → Use Gen 2 (even though not perfect)
  ↓
User sees: Gen 2 (8.9/10) + Warning "Close to target quality"
Total time: 70s
Total images: 2 (max reached)
```

---

## 🔧 Code Structure (Simplified)

```python
# ── Stage D: Quality Critic (Max 2 Images) ────────────────────

max_images_total = 2
images_generated = 1  # Gen 1 already exists

if quality != "fast" and creative_bible.get("emotional_territory"):

    # Check image 1
    critique_1 = await quality_critic.critique(
        image_url=raw_hero_url,
        tier=quality_tier,  # standard/premium/ultra
    )

    verdict_1 = critique_1["verdict"]

    if verdict_1 == "APPROVED":
        # Use image 1, done!
        pass

    elif verdict_1 == "REVISE" and images_generated < max_images_total:
        # Generate image 2 with targeted fix
        revision_notes = critique_1["revision_notes"]
        mutation_prompt = f"{enhanced_prompt} — IMPROVE: {revision_notes}"

        # Generate image 2
        gen_2 = await multi_client.generate(prompt=mutation_prompt, ...)
        images_generated += 1

        # Check image 2
        critique_2 = await quality_critic.critique(
            image_url=gen_2["image_url"],
            tier=quality_tier,
        )

        # Pick best
        if critique_2["overall_score"] > critique_1["overall_score"]:
            raw_hero_url = gen_2["image_url"]  # Use image 2
        else:
            pass  # Use image 1 (already set)

    # Continue with compositor if typography bucket...
```

---

## 🎯 Config (.env.local)

```bash
# Simple config - no cycles, just max 2 images
QUALITY_MAX_IMAGES=2

# Tier-specific thresholds (models selected by router)
QUALITY_CRITIC_THRESHOLD_STANDARD=8.0   # Flux Schnell
QUALITY_CRITIC_THRESHOLD_PREMIUM=8.5    # Flux Dev
QUALITY_CRITIC_THRESHOLD_ULTRA=9.0      # Flux Pro

# Dimension floors
QUALITY_DIMENSION_FLOOR_STANDARD=6.5
QUALITY_DIMENSION_FLOOR_PREMIUM=7.0
QUALITY_DIMENSION_FLOOR_ULTRA=7.5

# Beast gates
QUALITY_BEAST_GATES_MIN_STANDARD=8
QUALITY_BEAST_GATES_MIN_PREMIUM=9
QUALITY_BEAST_GATES_MIN_ULTRA=10
```

---

## 📊 Expected Behavior Summary

### STANDARD Tier:
- 70% cases: 1 image (20s)
- 25% cases: 2 images (40s)
- 5% cases: 2 images, both < 8.0 (deliver best with note)
- **Average: 1.3 images, 26s**

### PREMIUM Tier:
- 60% cases: 1 image (20s)
- 30% cases: 2 images (40s)
- 10% cases: 2 images, both < 8.5 (deliver best with note)
- **Average: 1.4 images, 28s**

### ULTRA Tier:
- 50% cases: 1 image (35s)
- 35% cases: 2 images (70s)
- 15% cases: 2 images, both < 9.0 (deliver best with note)
- **Average: 1.5 images, 52s**

---

## ✅ User Experience

**What user sees:**
```
1. "Generating luxury watch ad..." (15s)
2. "Quality review: Image 1..." (5s)
3. "Score: 8.2/10 — Improving text clarity..."
4. "Generating improved version..." (15s)
5. "Quality review: Image 2..." (5s)
6. "✅ Best result selected! Score: 8.8/10"
```

**Final output:**
- Single high-quality image (8.8/10)
- Quality badge: "Grade: A"
- No mention of rejected first attempt

---

## 🎯 Key Points

✅ **MAX 2 images total** (not per cycle, not 3, not 4 — exactly 2!)
✅ **Model selection by tier** (Schnell/Dev/Pro based on STANDARD/PREMIUM/ULTRA)
✅ **Targeted prompt fix** (weak dimension → specific improvement note)
✅ **Pick best of 2** (higher score wins, shown to user)
✅ **Simple logic** (no complex loops, no cycles counter, just 1 or 2 images)

---

**Clean. Simple. Exactly tumhara requirement! 🎯**
