# BEAST-Level Composition Intelligence v3 (Apr 8, 2026)

## The Revolution: Advertising = Text + Image as ONE Unified Composition

### Problem Solved

**OLD** (boring, rigid):
- Fixed positions ("text always at top")
- Same text amount for all images
- No context awareness
- Overlay feeling

**NEW** (BEAST intelligence):
- ✅ Dynamic text-image balancing
- ✅ Scene complexity analysis
- ✅ Visual focus detection
- ✅ Adaptive text strategy
- ✅ Natural integration

---

## How TOP Platforms Handle This

### 1. RECRAFT.AI (Advertising Specialist)
- Analyzes prompt → predicts scene complexity
- Complex scene → LESS text, smaller
- Simple scene → MORE text, larger
- Visual weight balancing

### 2. IDEOGRAM V3 (Marketing Mode)
- Product-focused → Text secondary
- Message-focused → Text primary
- Adapts to scene detail

### 3. ADOBE EXPRESS AI
- Finds "text zones" in composition
- Busy areas → avoid
- Clean areas → place text
- Dynamic sizing

---

## Our 3-Step Intelligence

```
STEP 1: Scene Complexity Analysis
├─ _analyze_scene_complexity()
├─ Returns: "clean" | "complex" | "balanced"
└─ Clean = more text possible, Complex = less text needed

STEP 2: Visual Focus Detection
├─ _detect_visual_focus()
├─ Returns: "text_primary" | "product" | "person" | "scene"
└─ Product = text secondary, Quote = text dominant

STEP 3: Text Strategy Decision
├─ _decide_text_strategy()
├─ Returns: {prominence, elements, size, composition, text_amount}
└─ Adaptive balance based on scene + focus
```

---

## Intelligence Examples

### TEXT-PRIMARY (Quote)
```
Input: "motivational quote BEAST MODE"
Analysis: scene=balanced, focus=text_primary
Strategy: prominence=DOMINANT, text_amount=minimal_elements
Result: "Typography is hero, minimal background, extra large bold text"
```

### PRODUCT FOCUS
```
Input: "luxury watch NEW COLLECTION"
Analysis: scene=clean, focus=product
Strategy: prominence=LOW, text_amount=minimal
Result: "Product-hero, text small and elegant, doesn't compete"
```

### COMPLEX SCENE
```
Input: "crowded street BIG SALE"
Analysis: scene=complex, focus=scene
Strategy: prominence=MEDIUM_HIGH, text_amount=minimal_to_medium
Result: "Bold text to compete with busy background"
```

### CLEAN PROMO
```
Input: "gradient 50% OFF sale"
Analysis: scene=clean, focus=scene, goal=sale_promotion
Strategy: prominence=HIGH, text_amount=medium_to_high
Result: "EXTRA-LARGE NUMBERS, all promo elements, urgent style"
```

---

## Special Features

### 1. Number Detection
```python
if "50% OFF" or "17 RECIPES" in headline:
    → EXTRA-LARGE BOLD NUMBERS for maximum impact
```

### 2. No Fixed Positions
```
BEFORE: "headline at top, CTA at bottom"
AFTER: "balanced composition, natural integration, clear hierarchy"
→ Let Ideogram decide optimal placement
```

### 3. Adaptive Text Amount
```
Product: headline + brand only
Promo: headline + value + CTA + brand
Quote: JUST the quote
```

---

## Comparison vs Competitors

| Feature | Canva | Midjourney | Ideogram | PhotoGenius v3 |
|---------|-------|------------|----------|----------------|
| Scene Analysis | ❌ | ❌ | ⚠️ | ✅ Auto |
| Focus Detection | ❌ | ❌ | ⚠️ | ✅ Explicit |
| Adaptive Balance | ⚠️ Templates | ❌ | ✅ | ✅ Intelligent |
| Number Prominence | ❌ | ❌ | ⚠️ | ✅ Auto-detects |
| Dynamic Position | ❌ Fixed | ✅ | ✅ | ✅ Guided |
| Context-Aware Text | ❌ | ❌ | ⚠️ | ✅ Full intelligence |

---

## Technical Details

**Files**: `apps/api/app/services/smart/design_agent_chain.py`

**Functions**:
- `_analyze_scene_complexity()`
- `_detect_visual_focus()`
- `_decide_text_strategy()`
- `_build_native_text_instructions()` (BEAST v3)

**Logging**:
```
[composition_intelligence] scene=clean focus=product prominence=low text_amount=minimal
```

---

## Results

**BEFORE v3**: Fixed, rigid, one-size-fits-all
**AFTER v3**: Dynamic, intelligent, context-aware

**This is how we BEAT top platforms!** 🚀💪

---

**Status**: ✅ PRODUCTION READY
**Date**: April 8, 2026
**Version**: v3.0 BEAST-Level
