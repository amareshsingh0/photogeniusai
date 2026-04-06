# 🎯 Triage Agent Enhancement Plan

**Reference:** [TriageAgentSkill.md](Agent Skill/TriageAgentSkill.md)
**Date:** April 7, 2026

---

## 📊 Gap Analysis

### Current Implementation
**File:** `design_agent_chain.py` → `_agent_triage()`

**What exists:**
- ✅ Platform detection (Instagram, Facebook, LinkedIn, etc.)
- ✅ Industry inference (fitness, food, fashion, etc.)
- ✅ Festival detection (is_festival, festival_name)
- ✅ Explicit text extraction (headline, CTA, subheadline)
- ✅ Goal classification (brand_awareness, sale_promotion, etc.)
- ✅ Audience (basic: b2b, b2c, youth, professional, general)

### Missing from TriageAgentSkill.md

#### 1. ❌ **Cultural Moment Detection** (Phase 1.4)
**Required:**
- Seasonal festivals (Diwali, Eid, Christmas, Holi, Navratri, etc.)
- Global moments (World Cup, Olympics, IPL, etc.)
- Industry moments (Sale season, product launch, etc.)
- Cultural codes (Indian market special)

**Current:** Basic festival detection only

---

#### 2. ❌ **Audience Intelligence** (Phase 1.5)
**Required:**
```json
{
  "age_range": [18, 35],
  "psychographic": "achiever | explorer | belonging-seeker | status-seeker | value-seeker",
  "cultural_context": "tier1_metro | tier2_india | global_english",
  "device_context": "mobile-first | desktop-work | large-screen-tv | outdoor",
  "attention_budget_seconds": 2
}
```

**Current:** Basic `"audience": "b2b|b2c|youth|professional|general"`

---

#### 3. ❌ **Emotional Target** (Phase 1.6)
**Required:** Single emotion from library:
```
urgency | desire | trust | curiosity | pride | nostalgia | aspiration |
belonging | exclusivity | joy | calm | power | rebellion | warmth |
awe | envy | fomo | comfort | excitement | reverence
```

**Current:** Not detected

---

#### 4. ❌ **Pipeline Routing** (Phase 2)
**Required:**
- `fast_path` - Low complexity, under 5 min
- `standard` - Default, 15-20 min
- `premium` - Complex, 30+ min
- `crisis` - Immediate, urgent

**Current:** All requests go through same pipeline

---

#### 5. ❌ **Variant Count** (Phase 1.1)
**Required:** `"variant_count": 3` (how many versions)

**User Requirement:** **MAX 2 images per generation** (Quality Critic testing)

**Decision:** **SKIP variant_count** - We generate max 2 images for quality testing, NOT multiple design variants

---

#### 6. ❌ **Urgency Classification** (Phase 1.1)
**Required:** `"urgency": "draft | standard | premium | critical"`

**Current:** Not detected

---

#### 7. ❌ **Comprehensive Output Schema** (Phase 3)
**Required:** Full structured package with:
- asset (type, platform, dimensions, format_output)
- brand (equity_constraints, brand_voice)
- audience (psychographic, device_context, attention_budget)
- creative_target (emotion, hook, cultural_moment, reference_aesthetics)
- constraints (mandatory_elements, forbidden_elements, char_limits)
- routing (skip_agents, priority_agents, parallel_phase_3, quality_passes)
- intelligence_flags (cultural_sensitivity, legal_review_needed, trend_alignment)

**Current:** Simple flat dict with 10-12 fields

---

## ✅ Enhancement Strategy

### Phase 1: Cultural Moment Detection
Add comprehensive festival/event detection:
- 15+ Indian festivals
- 10+ global moments
- Industry-specific moments
- Auto-inject festival palettes from brand_intelligence_agent

### Phase 2: Audience Intelligence
Add psychographic profiling:
- Age range inference from prompt
- Psychographic from industry + tone
- Cultural context (tier1_metro, tier2_india, etc.)
- Device context from platform
- Attention budget from platform type

### Phase 3: Emotional Target
Add emotion detection from goal + prompt:
- Sale → urgency
- Luxury → aspiration, desire
- Community → belonging, warmth
- Tech → trust, curiosity

### Phase 4: Pipeline Routing
Add intelligent routing based on:
- Complexity (simple post vs campaign)
- Brand (known vs unknown)
- Cultural sensitivity (festivals, identity)
- Urgency keywords ("ASAP", "urgent", "today")

### Phase 5: Enhanced Output Schema
Expand triage output to include all TriageAgentSkill.md fields

---

## 🚫 What We're NOT Implementing

1. **Variant Count** - User wants MAX 2 images for quality testing, not multiple design variants
2. **Multiple Asset Types** - Keep single asset focus
3. **Motion Assets** - Static images only (Sprint 3 future)
4. **Legal Review Flags** - Too complex for MVP

---

## 🎯 Implementation Plan

### Step 1: Create Enhanced Triage Knowledge Bases
- Cultural moments database
- Psychographic mapping
- Emotion detection rules
- Pipeline routing rules

### Step 2: Enhance _agent_triage()
- Add cultural moment detection
- Add audience intelligence
- Add emotional target
- Add pipeline routing
- Expand output schema

### Step 3: Wire into Design Chain
- Creative Director receives emotion target
- Brand Intel receives cultural moment
- Image Prompter receives reference aesthetics
- Quality Critic receives urgency for threshold tuning

---

## 📋 Priority Order

1. ✅ **Cultural Moment Detection** - HIGH (festivals boost engagement)
2. ✅ **Emotional Target** - HIGH (drives creative direction)
3. ✅ **Audience Intelligence** - MEDIUM (improves targeting)
4. ✅ **Pipeline Routing** - MEDIUM (optimizes resource use)
5. ⚠️ **Enhanced Schema** - LOW (nice-to-have structure)

---

## 🎯 Expected Output After Enhancement

### Before (Current):
```json
{
  "creative_type": "poster",
  "platform": "instagram_portrait",
  "goal": "sale_promotion",
  "audience": "general",
  "industry": "fashion",
  "is_festival": true,
  "festival_name": "diwali"
}
```

### After (Enhanced):
```json
{
  "creative_type": "poster",
  "platform": "instagram_portrait",
  "goal": "sale_promotion",
  "audience": "general",
  "industry": "fashion",

  // NEW: Cultural Moment
  "cultural_moment": {
    "type": "seasonal_festival",
    "name": "Diwali 2026",
    "palette_override": true,
    "keywords": ["celebration", "lights", "prosperity"]
  },

  // NEW: Emotional Target
  "emotion_target": "urgency",
  "hook": "Limited-time Diwali sale ends tonight",

  // NEW: Audience Intelligence
  "audience_intelligence": {
    "age_range": [25, 45],
    "psychographic": "value-seeker",
    "cultural_context": "tier1_metro",
    "device_context": "mobile-first",
    "attention_budget_seconds": 2
  },

  // NEW: Pipeline Routing
  "pipeline_mode": "standard",
  "urgency": "standard",
  "quality_passes": 1
}
```

---

**Next:** Implement Step 1 (Knowledge Bases) + Step 2 (Enhanced _agent_triage)
