# 🚀 Quick Start: Beast Mode Activation

**Status:** Ready to deploy (85% Beast Mode complete)

---

## ⚡ 3-STEP ACTIVATION

### STEP 1: Database Migration (5 minutes)
```bash
# Navigate to database package
cd C:\desktop\PhotoGenius AI\packages\database

# Run Prisma migration to add LearningLog + VisualDecree tables
npx prisma migrate dev --name add_learning_engine

# Generate Prisma client
npx prisma generate

# Verify schema
npx prisma studio
# Check that 'learning_logs' and 'visual_decrees' tables exist
```

### STEP 2: Environment Variables (2 minutes)
```bash
# Add to C:\desktop\PhotoGenius AI\apps\api\.env

# Learning Engine
LEARNING_ENGINE_ENABLED=true
LEARNING_MIN_SAMPLES=100
LEARNING_CONFIDENCE_THRESHOLD=0.75

# Quality Critic (should already be set)
QUALITY_CRITIC_THRESHOLD=8.5
QUALITY_DIMENSION_FLOOR=7.0
QUALITY_REVISION_MAX_CYCLES=3
QUALITY_GATES_MIN=9

# Design Director (auto-enabled)
ENABLE_DESIGN_DIRECTOR=true
ENABLE_MULTI_VARIANT=true
```

### STEP 3: Start API (1 minute)
```bash
# Navigate to API
cd C:\desktop\PhotoGenius AI\apps\api

# Start server
python -m uvicorn app.main:app --reload --port 8003

# Server should start with:
# [LearningEngine] Initialized (enabled=True)
# [design_chain] Design Director available
# [quality_critic] Initialized with 12 dimensions + 10 gates
```

---

## ✅ VERIFICATION TESTS

### Test 1: Health Check
```bash
curl http://localhost:8003/health
# Should return: {"status": "ok"}
```

### Test 2: Learning Analytics (Empty on First Run)
```bash
curl http://localhost:8003/api/v1/learning/analytics?days=30
```

**Expected Response:**
```json
{
  "total_generations": 0,
  "message": "No data"
}
```

### Test 3: Generate with Beast Mode (PREMIUM tier)
```bash
curl -X POST http://localhost:8003/api/v1/generate/stream \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "Tech startup launch poster with bold headline",
    "tier": "premium",
    "platform": "instagram",
    "width": 1080,
    "height": 1350
  }'
```

**Watch for SSE Events:**
1. `intent_ready` — Triage agent done
2. `brief_ready` — Creative Director + Design Director done
3. `generating` — fal.ai generation started
4. `quality_checking` — Quality Critic evaluating
5. `quality_scored` — Score + verdict returned
6. `final_ready` — Done

**Check Logs for:**
- `[design_chain] Design Director decree: hero_dominant`
- `[design_chain] Multi-variant mode: generating 3 layout variants`
- `[design_chain] Variant scores: safe=7.8, bold=8.5, disruptive=7.2 → winner: bold`
- `[quality_critic] Overall score: 8.7, verdict: APPROVED`

### Test 4: Verify Multi-Variant in Response
```bash
# In the final SSE event, check brief["_layout_variants"]

{
  "enabled": true,
  "winner": "bold",
  "scores": {
    "safe": 7.8,
    "bold": 8.5,
    "disruptive": 7.2
  }
}
```

### Test 5: Max 2 Images Verification
```bash
# Generate and watch logs

# You should see:
# "Quality review: Image 1/2"
# If REVISE verdict:
#   "Generating Image 2 with targeted improvements"
#   "Quality review: Image 2/2"
#   "PICK BEST OF 2: Image 2 selected (8.5 > 7.8)"

# If APPROVED verdict:
#   "Using Image 1 (score 8.7)"
```

---

## 🎯 WHAT'S ACTIVE

### ✅ Active Agents (9/10)
1. Triage Agent ✅
2. Brand Intel Agent ✅
3. Creative Director ✅
4. Design Director ✅ (NEW)
5. Cultural Intelligence ✅ (NEW)
6. Copy Writer ✅
7. Image Prompter ✅
8. Layout Planner ✅ (3 variants for PREMIUM+)
9. Quality Critic ✅ (12 dimensions + 10 gates)
10. Learning Engine ✅ (NEW)

### ✅ Active Features
- Max 2 images per generation (all tiers)
- Multi-variant layouts (PREMIUM/ULTRA only)
- Quality scoring (12 dimensions)
- Beast gates (10 standards)
- Cultural aesthetic detection (8 codes)
- Generational signals (Gen Z, Millennials, etc.)
- Platform contracts (Instagram, TikTok, LinkedIn, etc.)
- Learning logs (input + decisions + quality)
- Analytics (quality trends, top aesthetics, etc.)
- Recommendations (context-aware suggestions)

---

## 📊 TIER BEHAVIOR

### FAST Tier
- Flux Schnell (15s generation)
- Safe layout variant only
- Max 2 images
- Quality threshold: 8.0
- Beast gates: 8/10 minimum

### STANDARD Tier
- Flux Schnell (15s generation)
- Safe layout variant only
- Max 2 images
- Quality threshold: 8.0
- Beast gates: 8/10 minimum

### PREMIUM Tier ⭐
- Flux Dev (20s generation)
- **3 layout variants** (safe/bold/disruptive) → jury picks best
- Max 2 images
- Quality threshold: 8.5
- Beast gates: 9/10 minimum

### ULTRA Tier 💎
- Flux Pro (30s generation)
- **3 layout variants** (safe/bold/disruptive) → jury picks best
- Max 2 images
- Quality threshold: 9.0
- Beast gates: 10/10 minimum

---

## 🔧 TROUBLESHOOTING

### Issue: "design_director not available"
**Fix:** Check that `design_director.py` exists and imports correctly
```bash
python -c "from app.services.smart.design_director import design_director_agent; print('OK')"
```

### Issue: "Multi-variant mode not triggered"
**Fix:** Ensure `tier` is set to "premium" or "ultra" in request
```json
{
  "prompt": "...",
  "tier": "premium"  // NOT "standard"
}
```

### Issue: "Learning logs not saving"
**Fix:** Check Prisma migration ran successfully
```bash
cd packages/database
npx prisma studio
# Verify 'learning_logs' table exists
```

### Issue: "Quality Critic not running"
**Fix:** Check environment variable
```bash
echo $QUALITY_CRITIC_THRESHOLD
# Should output: 8.5
```

---

## 📈 MONITORING

### Key Metrics to Watch
1. **Quality Score Avg** (target: 8.5+)
   - Check: `/api/v1/learning/analytics` → `avg_quality_score`

2. **Beast Gates Pass Rate** (target: >90%)
   - Check: `/api/v1/learning/analytics` → `beast_gates_pass_rate`

3. **Variant Distribution** (expect: bold > safe > disruptive)
   - Check: `/api/v1/learning/analytics` → `layout_variant_distribution`

4. **Revision Rate** (target: <15%)
   - Check: Percentage of generations with `revision_cycles > 0`

5. **Images Per Generation** (enforce: ≤2)
   - Check logs for "Image 1/2" and "Image 2/2"

---

## 🎬 NEXT STEPS AFTER ACTIVATION

### Day 1: Monitor Logs
```bash
tail -f apps/api/logs/api.log | grep -E "design_chain|quality_critic|learning"
```

### Day 2: Check Analytics
```bash
curl http://localhost:8003/api/v1/learning/analytics?days=1
```

### Week 1: Analyze Patterns
- Which aesthetic codes are most used?
- Which layout variants win most often?
- What's the quality score trend?
- Are Beast gates passing consistently?

### Month 1: Optimize
- Tune quality thresholds if needed
- Adjust variant scoring weights
- Add new aesthetic codes
- Refine cultural intelligence

---

## 🦁 SUCCESS CRITERIA

### ✅ Beast Mode is ACTIVE when:
1. Quality scores avg 8.5+ (check analytics)
2. Beast gates pass >90% (check analytics)
3. Max 2 images per generation (check logs)
4. Multi-variant for PREMIUM+ (check logs: "generating 3 layout variants")
5. Learning logs accumulating (check DB: `SELECT COUNT(*) FROM learning_logs`)
6. Cultural aesthetics detected (check logs: "aesthetic_direction: ai_native")

### 🎯 You've Reached Beast Level when:
- Users say: "I don't know how you made this, but I want one."
- Quality is consistent (not random)
- Revisions are rare (<15%)
- Aesthetics feel 2026-native
- System learns from every generation

---

# 🚀 READY TO LAUNCH

**Current Status:** 85% Beast Mode
**Max Images:** 2 (enforced)
**Quality Standard:** 8.5/10 + 9/10 Beast gates
**Agents Active:** 9/10
**Learning:** Active

**LET'S GO. 🔥**
