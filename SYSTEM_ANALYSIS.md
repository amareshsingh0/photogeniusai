# PhotoGenius AI — Complete System Analysis & Issues Brief
**Date:** Apr 9, 2026 | **Version:** Post Flux 2 Pro Migration

---

## 1. CRITICAL BUG: Typography Model Override

### Problem
`generate_stream.py` **lines 307-313** has a HARDCODED Ideogram override that **bypasses** `config.py`:

```python
# generate_stream.py (LINE 307-313) — THE BUG
if bucket == "typography":
    fal_model_key = "ideogram_quality"          # ← HARDCODED! Ignores config
    model_label = _MODEL_LABELS.get("ideogram_quality", "Ideogram v3 Quality")
```

While `config.py` says:
```python
# config.py (LINE 672-677) — THE INTENDED CONFIG
"typography": {
    "fast":     {"model": "flux_2_pro", "provider": "multi"},
    "standard": {"model": "flux_2_pro", "provider": "multi"},
    "premium":  {"model": "flux_2_pro", "provider": "multi"},
}
```

### Impact
- **Config changes have ZERO effect** — Ideogram always used for typography
- **3.6x cost overrun**: $0.090 (Ideogram) vs $0.025 (Flux 2 Pro)
- Every test we ran was wasted because this override was never removed
- Frontend shows "Ideogram v3 Quality" because label resolves from hardcoded key

### Fix Required
Remove lines 307-313 hardcoded override, let config.py routing work naturally.

---

## 2. Complete Model Map

### Image Generation Models

| Model | Provider | Bucket | Cost | Quality |
|-------|----------|--------|------|---------|
| **Flux 2 Pro** | kie.ai → fal.ai | Typography (config), Photorealism premium | $0.025 | ⭐⭐⭐⭐⭐ text |
| **Flux 2 Dev** | Together AI → fal.ai | Artistic standard | $0.010 | ⭐⭐⭐⭐ |
| **Flux 2 Max** | BFL → fal.ai | Photorealism ultra | $0.060 | ⭐⭐⭐⭐⭐ |
| **Flux Schnell** | Pixazo → Fireworks → fal.ai | ALL fast tiers | $0.001 | ⭐⭐ |
| **Ideogram v3** | fal.ai | Typography (FORCED by bug) | $0.090 | ⭐⭐⭐ text |
| **Recraft v4** | fal.ai | Vector/SVG | $0.040 | ⭐⭐⭐⭐ |
| **Hunyuan** | fal.ai | Anime | $0.030 | ⭐⭐⭐ |
| **Imagen 3** | Google AI Studio | NOT WORKING (added, never connected) | $0.020 | ❌ |

### LLM Agents (ALL use Gemini 2.5 Flash)

| Agent | Role | Time | File |
|-------|------|------|------|
| Triage | 20+ field classification, cultural moments, emotion | ~4s | design_agent_chain.py |
| Brand Intel | Infer brand colors, tone, fonts | ~1.2s | design_agent_chain.py |
| Creative Director | Creative Bible (emotional territory, metaphors) | ~10-15s | design_agent_chain.py |
| Design Director | Visual system decree, composition archetype | ~0.5s | design_director.py |
| Copy Writer (BEAST) | Headline, CTA, body, features | ~8-13s | beast_copy_writer.py |
| Image Prompter (BEAST) | 9-step prompt with camera/lens library | ~18-20s | design_agent_chain.py |
| Layout Planner | Position text/logo (normalized coords) | ~12s | design_agent_chain.py |
| Char Guard | Platform character limits micro-agent | 0-13s | design_agent_chain.py |
| Quality Critic | 12-dimension scoring + 10 Beast gates | ~6-7s | quality_critic.py |

### Quality/Scoring

| Model | Purpose | Provider |
|-------|---------|----------|
| Groq Llama 3.2 Vision | Quality Critic primary | Groq |
| Gemini Vision | Quality Critic fallback | Google AI Studio |

---

## 3. Complete Pipeline Flow

```
USER PROMPT (e.g. "poster GRAND OPENING restaurant")
    │
    ▼
INTENT ANALYZER (heuristic, <0.2s)
    → creative_type=poster, is_ad=true, goal=event
    → SSE: intent_ready
    │
    ▼
CAPABILITY ROUTER (3-layer: LLM + pattern + keyword)
    → bucket="typography" (detected: poster/ad keywords)
    │
    ├── IF typography ──────────────────────────────┐
    │                                               │
    ▼                                               │
6-AGENT DESIGN CHAIN (~45-65s total)                │
    │                                               │
    ├─ Triage Agent (4s) → 20+ fields              │
    ├─ Brand Intel (1.2s) → colors, tone            │
    ├─ Creative Director (10-15s) → Creative Bible  │
    ├─ Design Director (0.5s) → composition decree  │
    ├─ Copy Writer (8-13s) → headline, CTA, body    │
    ├─ Char Guard (0-13s) → trim if over limit      │
    ├─ Design Room (0s) → backdrop scoring (Python)  │
    ├─ Typography Dir (0s) → fonts/effects (Python)  │
    ├─ Image Prompter (18-20s) ─┐ PARALLEL          │
    └─ Layout Planner (12s) ────┘                   │
    │                                               │
    → SSE: brief_ready                              │
    │                                               │
    ├── IF NOT typography ──────────────────────────┘
    │
    ▼
GEMINI PROMPT ENGINE (non-typography only)
    → Stage A: creative brief JSON
    → Stage B: model-specific params + CDI override
    │
    ▼
CDI MODEL SELECTION
    ⚠️ BUG: Typography = HARDCODED ideogram_quality (line 307-313)
    ⚠️ Config says flux_2_pro but NEVER USED for typography
    → SSE: generating
    │
    ▼
MULTI-PROVIDER CLIENT
    → Provider chain: kie.ai → fal.ai → Together → Replicate
    → Auto-failover on error
    → Returns: image_url, cost, generation_time
    │
    ▼
QUALITY CRITIC (if quality != "fast" AND creative_bible exists)
    → 12 dimensions: composition, color_authority, typography_excellence...
    → 10 Beast gates: stranger_test, scroll_stop, brand_DNA...
    → Verdict: APPROVED (≥8.5) / REVISE / ESCALATE
    → If REVISE: generate Image 2 with targeted fix (max 2 total)
    │
    ▼
POSTER COMPOSITOR → DISABLED (native text rendering)
    │
    ▼
SSE: final_ready → {image_url, ad_copy, poster_design, design_brief}
```

---

## 4. ALL Current Issues

### 🔴 CRITICAL

| # | Issue | File:Line | Impact |
|---|-------|-----------|--------|
| 1 | **Typography hardcoded to Ideogram** | generate_stream.py:307-313 | Config changes ignored, 3.6x cost |
| 2 | **Imagen 3 broken** (added but never connected) | multi_provider_client.py:592+ | Dead code, Google API not working |
| 3 | **Text rendering unreliable** (Ideogram typos) | AI model limitation | "GILDED SOON" instead of "SPOON" |

### 🟡 HIGH RISK

| # | Issue | File:Line | Impact |
|---|-------|-----------|--------|
| 4 | CDI parameter validation missing | generate_stream.py:329-331 | Bad steps/guidance → crash |
| 5 | Quality Critic revision = naive prompt mutation | generate_stream.py:520-538 | Low scores not properly fixed |
| 6 | KIE API response parsing fragile | multi_provider_client.py:495-540 | Format change = silent failure |
| 7 | Cost tracking hardcoded 0.0 | generate_stream.py:674-687 | No cost visibility |

### 🟢 MEDIUM RISK

| # | Issue | File:Line | Impact |
|---|-------|-----------|--------|
| 8 | No per-agent schema validation | design_agent_chain.py | Bad JSON = chain crash |
| 9 | Layout Planner often falls back to deterministic | design_agent_chain.py | Gemini JSON parse failures |
| 10 | Exchange rate INR hardcoded (84) | multi_provider_client.py:301 | Outdated cost display |
| 11 | No way to disable fal.ai/replicate providers | multi_provider_client.py:218-230 | No emergency kill switch |
| 12 | Compositor disabled but code still referenced | generate_stream.py:428-432 | Confusing codebase |
| 13 | User's detailed prompts completely rewritten | design_agent_chain.py | Expert prompts ignored |

---

## 5. Potential Future Issues

| Risk | Description | When |
|------|-------------|------|
| Gemini rate limiting | 3 keys rotating, but at scale (100+ req/hr) will hit limits | At scale |
| KIE API deprecation | Small provider, could shut down or change API | Anytime |
| Flux 2 Pro text quality | Good but not perfect — may need PIL compositor backup | Typography-heavy use |
| No image caching | Same prompt generates new image every time ($$$) | At scale |
| No A/B testing infra | Can't compare Flux vs Ideogram vs Imagen quality | When deciding models |
| Memory leak in agent chain | 10+ Gemini clients, no connection pooling cleanup | Long-running server |

---

## 6. Where Each Model Is Used

```
┌─────────────────────────────────────────────────────┐
│                    GEMINI 2.5 FLASH                  │
│  Used by: ALL 9 LLM agents + Gemini Prompt Engine   │
│  Keys: 3 rotating (GEMINI_API_KEY, _2, _3)          │
│  Cost: FREE tier (rate limited)                      │
│  Fallback: Heuristic (if Gemini fails)              │
└─────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────┐
│               IMAGE GENERATION MODELS               │
│                                                     │
│  Typography: Ideogram v3 (BUG) → should be Flux Pro│
│  Photorealism FAST: Flux Schnell ($0.001)           │
│  Photorealism STD: Flux 2 Dev ($0.010)              │
│  Photorealism PREM: Flux 2 Pro ($0.025)             │
│  Photorealism ULTRA: Flux 2 Max ($0.060)            │
│  Artistic: Flux 2 Dev/Max                           │
│  Anime: Hunyuan ($0.030)                            │
│  Vector: Recraft v4 ($0.040)                        │
│  Editing: Flux Kontext ($0.040)                     │
└─────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────┐
│               QUALITY CRITIC                        │
│  Primary: Groq Llama 3.2 Vision (fast, free tier)   │
│  Fallback: Gemini Vision (6-batch split)            │
│  Fires: quality != "fast" + creative_bible exists   │
└─────────────────────────────────────────────────────┘
```

---

## 7. Deep Research Prompt

Use this prompt for deep research to solve all issues:

```
I'm building PhotoGenius AI — an advanced AI image generation platform with:
- 10-agent design chain (Gemini 2.5 Flash for all LLM agents)
- Multi-provider image generation (fal.ai, kie.ai, Fireworks, Together, BFL, Replicate)
- Models: Flux 2 Pro/Dev/Max/Schnell, Ideogram v3, Recraft v4, Hunyuan
- Quality Critic: 12-dimension scoring + 10 Beast gates
- Typography bucket: poster/ad text rendering via AI models

CURRENT CRITICAL ISSUES:

1. TEXT RENDERING ACCURACY: AI models (Ideogram v3, Flux 2 Pro) make spelling
   errors when rendering text in images. "THE GILDED SPOON" becomes "THE GILDED SOON".
   Contradictory CTAs appear ("NOW OPEN" + "OPENING SOON" together).

   Questions:
   - What is the BEST model for text rendering in AI-generated images in 2026?
   - How do professionals handle text-in-image accuracy?
   - Should I use a hybrid approach (AI image + PIL text overlay)?
   - How does Ideogram v3 compare to Flux 2 Pro for text accuracy?
   - Are there prompt engineering techniques to improve text spelling accuracy?
   - Should I use Google Imagen 3 via Vertex AI for better text? How to integrate?

2. PROMPT QUALITY: User writes "restaurant promotion GRAND OPENING Free Dessert"
   but agent chain generates dessert closeup instead of restaurant interior with
   celebration atmosphere. Agents rewrite user intent too aggressively.

   Questions:
   - How to balance agent creativity vs user intent preservation?
   - Should detailed user prompts (>150 words) bypass agent chain?
   - What's the best approach for intent-preserving prompt enhancement?
   - How do Midjourney/Leonardo/ChatGPT handle user prompt preservation?

3. GOOGLE IMAGEN 3 INTEGRATION: I have Google AI Studio API keys (same as Gemini
   LLM keys). Want to use Imagen 3 for image generation.

   Questions:
   - What is the EXACT REST API endpoint for Imagen 3 via Google AI Studio?
   - What is the correct payload format? (prompt, aspect_ratio, safety settings)
   - Does Imagen 3 return URLs or base64?
   - What are the rate limits and pricing on free/paid tiers?
   - Does google-generativeai Python SDK support image generation? How?
   - Is Imagen 3 available on fal.ai or only Google?

4. QUALITY CRITIC IMPROVEMENT: Currently uses Groq Llama 3.2 Vision for scoring.
   Revision routing is naive (just mutates prompt instead of routing to specific agents).

   Questions:
   - What is the best vision model for image quality assessment in 2026?
   - How to implement smart revision routing (low composition → re-layout)?
   - Should revision use inpainting (fix specific region) vs full regeneration?
   - How many revision cycles are optimal before diminishing returns?

5. COST OPTIMIZATION: Currently Ideogram v3 costs $0.09/image for typography.
   Need to reduce to <$0.03/image without quality loss.

   Questions:
   - Flux 2 Pro via kie.ai at $0.025 — is text quality comparable to Ideogram?
   - Are there even cheaper providers for Flux 2 Pro?
   - Should I implement image caching for similar prompts?
   - What's the cost structure for Google Imagen 3?

6. PIL COMPOSITOR vs NATIVE TEXT: Currently PIL compositor is DISABLED.
   AI models render text natively but with spelling errors.

   Questions:
   - Should I use hybrid approach: AI renders scene, PIL overlays exact text?
   - How to blend PIL text naturally with AI-generated backgrounds?
   - What techniques make PIL text overlay look professional (not pasted-on)?
   - Should I use CSS/SVG rendering instead of PIL for better typography?

Search for latest 2026 documentation, benchmarks, and best practices.
Focus on production-ready solutions, not experimental approaches.
```

---

## 8. Priority Fix Order

| Step | Action | Time | Impact |
|------|--------|------|--------|
| 1 | **Remove hardcoded Ideogram override** (generate_stream.py:307-313) | 5 min | Config changes actually work |
| 2 | **Test Flux 2 Pro** for typography | 2 min | 72% cost reduction + better text |
| 3 | **Add PIL compositor hybrid mode** | 30 min | 100% text accuracy for brand/CTA |
| 4 | **Add Gemini call timeouts** | 10 min | No more hanging pipelines |
| 5 | **Fix CDI parameter validation** | 15 min | No more crash on bad values |
| 6 | **Implement smart revision routing** | 1 hr | Better quality scores |
| 7 | **Wire cost tracking** | 20 min | Cost visibility |
| 8 | **User prompt preservation mode** | 30 min | Expert prompts respected |
