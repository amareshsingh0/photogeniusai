# 🎯 Beast-Level Prompt Engineer — Gap Analysis

**Date:** April 7, 2026
**Reference:** [SeniorPromptEngineer.md](Agent Skill/SeniorPromptEngineer.md)
**Current File:** `apps/api/app/services/smart/design_agent_chain.py` → `_agent_image_prompter()`

---

## 📊 Current vs Required

### ✅ What We Have (Strong Foundation)

| Feature | Status | Notes |
|---------|--------|-------|
| Model Selection Guide | ✅ **100%** | flux_schnell/dev/pro/max, hunyuan, ideogram, recraft |
| Per-Model Templates | ✅ **100%** | 3-part for Flux Pro, 2-part for Dev, etc. |
| Subject-First Rule | ✅ **100%** | Enforced in KB |
| Bottom-Dark Engineering | ✅ **100%** | "lower 50% naturally dark" rule |
| CD → Image Prompt Translation | ✅ **100%** | emotional_territory, visual_metaphors, composition |
| Basic Negative Prompts | ✅ **80%** | Generic + per-model basics |
| Hex → Natural Language | ✅ **100%** | Implemented in gemini_prompt_engine.py |

### ❌ What We're Missing (Beast Components)

| Feature | Status | Priority | Source |
|---------|--------|----------|--------|
| **9-Step Build Process** | ❌ **0%** | **P0** | SeniorPromptEngineer.md lines 273-372 |
| **Camera/Lens Reference Library** | ❌ **0%** | **P1** | lines 293-305 |
| **Power Modifiers (Flux Pro)** | ⚠️ **30%** | **P1** | lines 103-109 |
| **Quality Stack (Top Tier Signals)** | ⚠️ **20%** | **P1** | lines 343-354 |
| **India Market Prompt Library** | ❌ **0%** | **P0** | lines 424-449 |
| **Enhanced Negative Prompts** | ⚠️ **40%** | **P1** | lines 79-82, 179-180, 257-266 |
| **Style Register Translation** | ⚠️ **50%** | **P2** | lines 326-339 |
| **Weighted Prompts (SDXL)** | ❌ **0%** | **P3** | lines 248-256 |
| **Continuous Learning Protocol** | ❌ **0%** | **P2** | lines 453-468 |

---

## 🔧 Required Enhancements

### 1. Camera/Lens Reference Library (P1)

**Missing:** Specific camera & lens models that work with AI

**Add to KB:**
```python
CAMERA_REFERENCES = {
    "portrait": ["Leica M11", "Hasselblad X2D", "Sony A7R V"],
    "fashion": ["Phase One IQ4", "Fujifilm GFX 100S"],
    "street": ["Leica Q3", "Sony A7 IV", "Ricoh GR III"],
    "product": ["Hasselblad H6D-400c", "Phase One XT", "Cambo Actus"],
    "cinematic": ["ARRI Alexa 35", "RED V-RAPTOR", "Sony VENICE 2"],
}

LENS_REFERENCES = {
    "bokeh": ["85mm f/1.2", "105mm f/1.4"],
    "wide": ["24mm f/1.4", "35mm f/1.4"],
    "telephoto": ["200mm f/2.8"],
    "macro": ["100mm macro, 1:1 ratio"],
}
```

**Usage:**
"Shot on Hasselblad X2D, 85mm f/1.4" → Worth 50 other modifiers combined

---

### 2. Power Modifiers (Flux Pro Enhancement)

**Current:** Basic modifiers only
**Missing:** Flux Pro advanced modifiers

**Add to KB:**
```
FLUX_PRO_POWER_MODIFIERS:
  - "[Color] Pantone [XXX]" — model responds to Pantone references
  - "hyper-detailed [material texture]" — glass, fabric, metal
  - "subsurface scattering" — for skin that looks real (not plastic)
  - "chromatic aberration, subtle" — lens authenticity
  - "[photographer name] photography" — style transfer (Annie Leibovitz, Roger Deakins, etc.)
```

---

### 3. Quality Stack (Top Tier Signals)

**Current:** Generic "photorealistic, 8K" type modifiers (explicitly warned against)
**Missing:** Professional quality signals that actually work

**Add to KB:**
```
TOP TIER QUALITY SIGNALS (use max 5):
  ✅ "award-winning commercial photography"
  ✅ "published in [Vogue/WIRED/Wallpaper*/Kinfolk]"
  ✅ "[Photographer name] photography" (Annie Leibovitz, Steve McCurry, etc.)
  ✅ "medium format photography"
  ✅ "color graded by [reference]"

DO NOT USE (overused, weak signal):
  ❌ "hyperrealistic" | "8K" | "trending on artstation" | "masterpiece" |
  ❌ "best quality" | "ultra detailed" — these are NOISE
```

---

### 4. India Market Prompt Library (P0 - CRITICAL)

**Missing:** Cultural authenticity for Indian market

**Add to KB:**
```python
INDIA_PROMPTS = {
    "faces": {
        "template": "Indian {gender}, {age} years old, {skin_tone}, {region} aesthetic, {expression}, {styling}",
        "skin_tones": ["warm brown", "medium brown", "deep brown", "golden brown"],
        "regions": ["South Indian", "North Indian", "Bengali", "Punjabi", "Marathi"],
        "styling": ["contemporary urban", "traditional", "fusion"],
        "forbidden": ["exotic", "dusky", "ethnic"],  # Colonial/othering language
    },
    "settings": {
        "modern": "Contemporary Mumbai apartment, floor-to-ceiling windows, city skyline, clean lines, warm afternoon light",
        "heritage": "Haveli interior, Rajasthan, carved sandstone arches, jali screens, colored glass shadows, antique brass fixtures",
        "festival": "Diwali decorated courtyard, clay diyas in rows, marigold garlands, rangoli pattern, families in soft focus",
        "street": "Colaba Causeway/Linking Road/Sarojini Nagar, colorful stalls, monsoon-wet streets, golden evening light",
    },
}
```

---

### 5. Enhanced Negative Prompts (P1)

**Current:** Generic negatives
**Missing:** Model-specific artifact targeting

**Add to KB:**
```
NEGATIVE_PROMPTS_ENHANCED:

  # Flux (all variants)
  BASE: "watermark, signature, text, username, artist name"
  PORTRAIT_ADD: "plastic skin, smooth skin, overexposed highlights, blown-out whites,
                  lens distortion, unnatural poses"
  PRODUCT_ADD: "floating elements, merged objects, inconsistent shadows"

  # SDXL (if used)
  ARTIFACT_TARGETING: "EasyNegative, ng_deepnegative_v1_75t, (bad-hands-5:1.0),
                        (worst quality:2), (low quality:2), skin spots, acnes,
                        (ugly:1.331), (duplicate:1.331), mutated hands,
                        (poorly drawn hands:1.5), extra limbs, cloned face,
                        (fused fingers:1.61521), (too many fingers:1.61521)"

  # Ideogram
  ANTI_PHOTO: "photorealistic, lens blur, noise, photography, camera artifacts"

  # Hunyuan
  LIGHTING_FIX: "harsh lighting, overexposed skin, cartoon, anime, illustration"
```

---

### 6. 9-Step Build Process (P0 - STRUCTURAL)

**Current:** Prompt built ad-hoc
**Missing:** Explicit 9-step methodology

**Implement as systematic process:**

```
STEP 1: Subject Core
  → Extract from Design Director brief
  → 2-3 sentences with hyper-specific physical attributes
  → Example: "Indian woman, 28 years old, sari in deep magenta silk, carrying woven basket"

STEP 2: Environment/Setting
  → NOT "outdoors" — "narrow street in Mumbai's Colaba market, monsoon-wet cobblestones"

STEP 3: Lighting (MOST IMPORTANT)
  → Source: sun/studio/neon/natural
  → Direction: from upper-left/backlit/frontal/below
  → Quality: hard/soft/diffused/harsh
  → Color temp: warm 3200K/neutral 5600K/cool 8000K
  → Shadows: deep/subtle/absent

STEP 4: Camera/Lens
  → "Shot on [camera] + [lens spec]"
  → Pick from CAMERA_REFERENCES based on industry

STEP 5: Composition
  → Translate CD's composition archetype:
    hero-dominant → "subject centered, full-frame, minimal background"
    editorial split → "left third [X], right two-thirds [Y]"
    dynamic diagonal → "diagonal composition, subject angled 45°"

STEP 6: Color Palette Translation
  → Convert hex to descriptive language
    #1A1035 → "deep obsidian navy background, almost black with blue undertone"
    #F4A62A → "warm amber gold accent, like diya flame illumination"

STEP 7: Style Register
  → Map CD's aesthetic to model vocabulary
    "brutalism × luxury" → "raw concrete, architectural negative space, expensive materials, editorial quality"

STEP 8: Quality Stack
  → Add 3-5 top-tier quality signals (NOT generic ones)

STEP 9: Final Assembly
  → Combine all elements
  → Validate: subject first, bottom dark, zero text keywords, model-appropriate length
```

---

## 📁 Implementation Plan

### Phase 1: Knowledge Base Expansion (1-2 hours)
1. Add `CAMERA_REFERENCES` dict
2. Add `LENS_REFERENCES` dict
3. Add `FLUX_PRO_POWER_MODIFIERS` list
4. Add `QUALITY_STACK_APPROVED` / `QUALITY_STACK_FORBIDDEN` lists
5. Add `INDIA_PROMPTS` comprehensive dict
6. Expand `NEGATIVE_PROMPTS_ENHANCED` with model-specific targeting

### Phase 2: Prompt Build Process Enhancement (2-3 hours)
1. Add explicit 9-step build function: `_build_prompt_9_steps()`
2. Integrate with existing `_agent_image_prompter()`
3. Each step returns intermediate output for debugging

### Phase 3: Style Register Translation (1 hour)
1. Add CD aesthetic → model vocabulary mapping
2. Examples: brutalism×luxury, bio-organic premium, retro-future Y2K

### Phase 4: Testing & Validation (1 hour)
1. Test 20 sample prompts through 9-step process
2. Validate model-specific outputs
3. Compare old vs new prompt quality

---

## 🎯 Success Criteria

**Before (Current):**
```
"A luxury watch resting on dark slate, single spotlight from above, photorealistic,
high quality, professional photography"
```
**Word count:** 15 words
**Quality signals:** Generic
**Lighting specificity:** Low
**Camera ref:** None

**After (Beast-Level):**
```
"Luxury Swiss watch with exposed mechanical movement, brushed titanium case,
resting on black slate surface at 15° angle. Single key light from 45° upper left,
3200K warm tungsten, creating sharp shadow extending lower right, subtle fill
light preventing pure black. Shot on Phase One XT, 100mm macro lens at 1:1 ratio,
f/2.8, revealing gear teeth texture. Editorial watch photography, published in
Wallpaper* magazine aesthetic, Kodak Portra color grading, warm metal tones,
deep shadow graduation, medium format quality."
```
**Word count:** 85 words
**Quality signals:** Phase One XT, Wallpaper* magazine, Kodak Portra (3 top-tier)
**Lighting specificity:** HIGH (source, angle, temp, shadow direction, fill ratio)
**Camera ref:** Phase One XT, 100mm macro, f/2.8, 1:1 ratio

---

## 📊 Impact Metrics

| Dimension | Before | After | Improvement |
|-----------|--------|-------|-------------|
| **Prompt Specificity** | 3/10 | 9/10 | 3× |
| **Lighting Detail** | Generic | 5-point spec | ∞ |
| **Camera Reference** | None | Model + lens + settings | ∞ |
| **Quality Signals** | Generic noise | 3-5 top-tier | 10× |
| **Cultural Authenticity (India)** | None | Comprehensive library | ∞ |
| **Negative Prompt Precision** | Generic | Model-specific artifacts | 5× |

---

## 🚀 Next Steps

1. ✅ **Read all reference docs** (DONE)
2. 🔧 **Expand _IMAGE_PROMPT_ENGINEER_KB** with missing knowledge bases
3. 🔧 **Implement 9-step build process** as explicit function
4. 🔧 **Integrate India market prompts** for cultural authenticity
5. 🔧 **Test with 20 sample briefs** (fashion, food, tech, festival)
6. 🔧 **Update MEMORY.md** with Beast-Level Prompt Engineer

---

**Status:** Ready for implementation
**Estimated Time:** 4-6 hours total
**Priority:** P0 (India market prompts critical for PhotoGenius AI's target market)
