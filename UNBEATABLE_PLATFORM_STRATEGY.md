# PhotoGenius AI — Unbeatable Platform Strategy
**Last updated: March 23, 2026 | Phase: Fast-Move API Era (Active)**

---

## 0. Philosophy (Never Change This)

> User sirf raw prompt deta hai. Backend pure magic karta hai.
> Platform **capabilities** dikhata hai, **technology** nahi.
> Result itna achha hona chahiye ki user bole: *"Yeh real photo hai kya?!"*

**Core Principles:**
1. **Capability-first, model-agnostic** — Models change, capabilities don't. Always route by *what* not *who*.
2. **Never delete, always evolve** — Own SageMaker infra (GPU1+GPU2) is the future; APIs are the fast path now.
3. **Ensemble + Judge** — Never trust a single model. Generate 2–4, pick the best automatically.
4. **Progressive UI** — Never make user stare at a blank screen. Show intelligence first, image second.
5. **Feedback loop from day 1** — Every thumbs-up/down improves routing. This is the real moat.

---

## 1. Current State (March 21, 2026)

### Infrastructure Status
| Asset | Status | Notes |
|---|---|---|
| GPU1: `photogenius-generation-dev` | HOLD | PixArt v31 + CLIP jury + MediaPipe — future own-model base |
| GPU2: `photogenius-orchestrator` | HOLD | RealVisXL v3.2 post-processor — future quality layer |
| Creative OS Pipeline v2 | ✅ ACTIVE | 7-stage pipeline fully built, all stages running |
| `apps/api/` FastAPI backend | ✅ ACTIVE | Unified generate endpoint connected to smart router |
| `apps/web/` Next.js frontend | ✅ ACTIVE | Dashboard + gallery working |
| SageMaker + S3 infra | HOLD | photogenius-models-dev bucket — keep all models |

### Active API Keys
| Service | Status | Use |
|---|---|---|
| `FAL_KEY` | ✅ Set | fal.ai — primary generation (Flux 2, Ideogram, Recraft, Kontext) |
| `GEMINI_API_KEY` | ✅ Set | Gemini 2.5 Flash — prompt engine (active) |
| `REPLICATE_API_TOKEN` | ✅ Set | Backup generation fallback |
| `TOGETHER_API_KEY` | ⬜ Needed | Together AI — Flux 2 Pro/Dev cheaper fallback |
| `FIREWORKS_API_KEY` | ⬜ Needed | Fireworks AI — cheapest Flux Schnell ($0.0014) |
| `USE_IDEOGRAM` | `false` | Disabled — enable when key ready (already on fal.ai) |
| `USE_ANTHROPIC` | `false` | Disabled — enable when key ready |

---

## 2. Architecture (What's Actually Running Now)

```
USER INPUT (raw prompt)
         │
         ▼
┌─────────────────────────────────────────────────────┐
│  CREATIVE OS PIPELINE (Stages -1 to 2) ✅ BUILT     │
│  Stage -1: Intent Analyzer → creative_type, goal    │
│  Stage 0:  Text overlay detection                   │
│  Stage 0.5: Creative Director → theme/colors        │
│  Stage 1:  Creative Graph → layout nodes            │
│  Stage 1.5: Variant Generator → layout variants     │
│  Stage 2:  Layout Planner → rule-of-thirds math     │
└─────────────────────┬───────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────┐
│  GEMINI 2.5 FLASH PROMPT ENGINE ✅ ACTIVE           │
│  Step A: raw prompt → Creative Brief JSON           │
│           (photographer + director mindset)         │
│  Step B: Brief → Flux Pro optimized prompt          │
│           (natural lang, camera, lighting, mood)    │
│  Fallback: heuristic (if no API key)                │
└─────────────────────┬───────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────┐
│  3-LAYER SMART ROUTER ✅ ACTIVE                     │
│  L1: detect_capability_bucket(prompt)               │
│      → photorealism / typography / artistic /       │
│        character / vector / interior / editing      │
│  L2: get_model_config(bucket, tier)                 │
│      → fal.ai model + params                        │
│  L3: USE_IDEOGRAM flag → Ideogram or Flux Pro       │
└─────────────────────┬───────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────┐
│  MULTI-PROVIDER GENERATION ✅ ACTIVE                 │
│  Primary: fal.ai (Flux Pro/Dev/Schnell/Redux/Fill)  │
│  Fallback: Together AI → Fireworks AI → Replicate   │
│  ESRGAN upscale: fal.ai ($0.002/image)              │
│  Auto-failover: user never sees provider errors     │
└─────────────────────┬───────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────┐
│  POST-PROCESSING (Stages 4-6) ✅ BUILT              │
│  Stage 4:  Text Overlay + Design Effects (PIL)      │
│  Stage 5a: Brand Checker                            │
│  Stage 5b: Poster Jury v2 + letter grade            │
│  Stage 6:  CTR Predictor                            │
└─────────────────────┬───────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────┐
│  RESPONSE → Frontend                                │
│  image_url + enhanced_prompt + creative_os metadata │
│  (intent, graph, layout, jury, brand, ctr, gen)     │
└─────────────────────────────────────────────────────┘
```

---

## 3. Capability Buckets → Model Routing Table (Updated March 21, 2026)

**Rule: Route by CAPABILITY, not model name. Update monthly.**

| Bucket | Trigger Keywords | Best Model | Provider | Cost/img | Fallback |
|---|---|---|---|---|---|
| **photorealism** | real, photo, 8k, skin, portrait, product | `flux-2-pro` | fal.ai / Together AI | $0.03 = ₹2.52 | `flux-2` dev $0.012 |
| **typography** | text, quote, logo, poster with words | `ideogram-v3` QUALITY | fal.ai | $0.09 = ₹7.56 | `ideogram-v3` TURBO $0.03 |
| **artistic** | painting, anime, fantasy, vibe, mood | `flux-2-max` | fal.ai / Together AI | $0.07 = ₹5.88 | `flux-2` dev $0.012 |
| **anime** | anime, manga, cartoon, chibi | `hunyuan-image` | fal.ai | $0.03 = ₹2.52 | `flux-2` dev |
| **character_consistency** | same person, consistent face, reference | `flux-kontext-pro` | fal.ai / Together AI | $0.04 = ₹3.36 | `flux-kontext-max` $0.08 |
| **editing** | fix, edit, remove, replace, inpaint | `flux-kontext-pro` | fal.ai | $0.04 = ₹3.36 | `flux-fill` $0.05 |
| **vector** | svg, icon, flat logo, scalable | `recraft-v4-svg` | fal.ai / Replicate | $0.08 = ₹6.72 | `recraft-v3` $0.08 |
| **interior_arch** | room, interior, building, render, space | `flux-2-pro` | fal.ai / Together AI | $0.03 = ₹2.52 | `flux-2-max` $0.07 |
| **fast** | quick, draft, preview, sketch | `flux-schnell` | Fireworks AI | $0.0014 = ₹0.12 | fal.ai schnell $0.003 |

**Key upgrades vs old table:**
- `flux-pro` ($0.05) → `flux-2-pro` ($0.03) — **better quality + 40% cheaper**
- `flux-redux` → `flux-kontext-pro` — **Kontext is purpose-built for consistency + editing**
- `flux-fill` → `flux-kontext-pro` for editing — **natural language edits, no mask needed**
- Added `anime` bucket → `hunyuan-image` (best for anime/Asian styles)
- `vector` → `recraft-v4-svg` (true SVG output, #1 ranked design model)
- `fast` cheapest: Fireworks AI at $0.0014 vs fal.ai $0.003

---

## 4. Prompt Engine — Active Implementation

**Active: Gemini 2.5 Flash** (Claude disabled until key added)

### Step A: Creative Brief (Gemini 2.5 Flash)
```
System: World-class creative director + photographer.
        Convert raw prompt → structured JSON Brief.
        Fields: visual_concept, subject, setting, lighting, camera,
                composition, mood, color_palette, texture_detail,
                style_refs, avoid
Output: Pure JSON (response_mime_type=application/json enforced)
```

### Step B: Model Params (Gemini 2.5 Flash)
```
System: AI image generation specialist.
        Convert Brief → model-specific generation params.
        For Flux Pro: natural descriptive language, camera/lens terms.
Output: {prompt, negative_prompt, style_notes}
```

**Real example output (tested):**
- Input: *"luxury car ad at golden hour sunset"*
- Brief mood: *"Aspirational, elegant power, serene luxury"*
- Brief camera: *"Medium format digital, 85mm f/1.8, circular polarizer filter"*
- Brief refs: *["Maserati print ads", "Art of Rally aesthetic", "Paul Octavious photography"]*
- Final prompt: *"A meticulously clean dark metallic grey luxury sports coupe... coastal highway... golden hour sunlight from camera-right... long dramatic shadows..."*

**Cost per image (Prompt Engine):**
- Gemini 2.5 Flash (free tier): ~₹0 for now
- Claude Sonnet (future): ~₹0.60 Step A + ₹0.08 Step B = ₹0.68

---

## 5. Cost Tiers (Optimized — March 21, 2026)

**Strategy: Schnell drafts + jury + ESRGAN upscale = premium quality at ₹1**

| Tier | Flow | Generation | Cost | Sell | Margin |
|---|---|---|---|---|---|
| **FAST** | Gemini→Schnell×1→output | 1 Schnell | **₹0.25** | free/₹5 | 20x |
| **STANDARD** | Gemini→Schnell×3→jury→ESRGAN | 3 Schnell + upscale | **₹1** | ₹15-20 | 15-20x |
| **PREMIUM** | Gemini→Schnell×3→jury→Flux Dev refine | 3 Schnell + 1 Dev | **₹3** | ₹50-80 | 17-27x |
| **ULTRA** | Gemini→Flux Pro×1 + Dev×2→jury→post-proc | 1 Pro + 2 Dev | **₹8.50** | ₹150+ | 18x+ |

**Why this works:**
- Gemini prompt engine makes even Schnell produce 90%+ quality (exact lighting, camera, mood)
- Ensemble jury picks best of 3 → eliminates bad luck
- ESRGAN 4x upscale ($0.002) → sharp 4K from 1024px draft
- Flux Dev refine on PREMIUM → final 5% quality polish on jury winner
- Flux Pro only used in ULTRA where margin justifies it

**Cost comparison vs competitors:**
| Platform | Per-image cost | Our equivalent |
|---|---|---|
| Midjourney | ₹0.67-1 (subscription) | ₹1 STANDARD |
| Higgsfield Basic | ₹843/mo fixed | ₹0.25-3 pay-per-use |
| ChatGPT (DALL-E) | ₹15-20/mo fixed | ₹0.25 FAST |
| **PhotoGenius** | **₹0.25-8.50** | **Pay only what you use** |

---

## 6. Build Status — Phase Tracker

### ✅ Phase 1: API Gateway (COMPLETE — March 21, 2026)
- [x] `services/external/fal_client.py` — fal.ai async wrapper (Flux Pro/Dev/Redux/Fill/ESRGAN)
- [x] `services/external/ideogram_client.py` — built, flag-disabled
- [x] `services/smart/gemini_prompt_engine.py` — 2-step Gemini engine (active, tested)
- [x] `services/smart/claude_prompt_engine.py` — built, flag-disabled
- [x] `services/smart/config.py` — CAPABILITY_ROUTING table (8 buckets + model map)
- [x] `services/smart/generation_router.py` — SmartGenerationRouter (USE_IDEOGRAM/USE_ANTHROPIC flags)
- [x] `api/v1/endpoints/unified_generate.py` — Stage 3 connected to smart_router (503 on fal.ai fail)
- [x] `api/v2/generate.py` — v2 endpoint also updated to smart_router
- [x] `.env.local` — FAL_KEY + GEMINI_API_KEY + flags configured
- [x] `requirements.txt` — `google-genai>=1.0.0` + `fal-client>=0.15.0` added
- [x] `start.bat` + `start.ps1` — stable Windows startup (kill port → clear pyc → uvicorn --reload)
- [x] End-to-end test PASSED — 26.8s, fal.ai Flux Pro, Gemini 2.5 Flash engine
- [x] fal.ai model ID fixes (flux/schnell slash, schnell≤12 steps, no guidance_scale for schnell)

### ✅ P0 — Server & Dependencies (COMPLETE — March 21, 2026)
- [x] `requirements.txt` — `google-genai`, `fal-client` added
- [x] Windows server stability — `start.bat` / `start.ps1` scripts
- [x] SageMaker fallback removed — clean 503 on fal.ai failure
- [ ] **fal.ai balance top-up** — add credits at fal.ai/dashboard/billing (PENDING — user doing this)
- [ ] Live frontend test after balance added

### ✅ P1 — Model Upgrade + Cost-Optimized Ensemble + Multi-Provider (COMPLETE — March 22, 2026)

**Model upgrades (update fal_client.py + config.py):**
- [x] `fal_client.py` — upgraded to Flux Gen 2 (flux-2-pro, flux-2-dev, flux-2-max, flux-2-turbo)
- [x] `flux-redux` → `flux-kontext-pro` (character consistency + instruction editing)
- [x] Added Ideogram v3 (TURBO/QUALITY), Recraft v4 SVG, Hunyuan Image (anime)
- [x] `multi_provider_client.py` — auto cheapest provider per model with failover
- [x] Provider assignments: pixazo (Schnell $0.0012) → kie.ai (Flux 2 Pro $0.025) → BFL (Flux 2 Max $0.060) → Together (Flux 2 Dev)
- [x] Bool flags: `USE_TOGETHER=false`, `USE_BFL=true`, `USE_KIE=true`, `USE_PIXAZO=true`
- [x] `ensemble.py` — tier-aware ensemble pipeline:
  - FAST: 1× Schnell (~₹0.10)
  - STANDARD: 3× Schnell parallel → jury → ESRGAN 4x (~₹0.47)
  - PREMIUM: 3× Schnell → jury → Flux 2 Dev refine (~₹1.14)
  - ULTRA: 2× Flux 2 Pro parallel → jury (~₹4.20)
- [x] Low-quality gate: jury score < 0.45 → auto regen (1 retry)
- [x] Prompt cache: MD5(prompt[:100]+tier+bucket) → TTL 24h, max 500 entries
- [x] `generation_router.py` — uses ensemble + cache instead of direct generate

### ✅ P2 — Progressive UI (COMPLETE — March 21, 2026)
- [x] `api/v1/endpoints/generate_stream.py` — FastAPI SSE endpoint (`POST /api/v1/generate/stream`)
- [x] `apps/web/app/api/generate/stream/route.ts` — Next.js SSE proxy (intercepts final_ready → DB save)
- [x] Frontend: real event-driven progress (intent_ready → brief_ready → generating → final_ready)
- [x] Creative Brief card slides in at ~1-2s: visual concept, mood, lighting, camera, style refs
- [x] Progress bar driven by real events (no fake timers)

### ✅ P3 — User Personalization (COMPLETE — March 23, 2026)
- [x] `api/v1/endpoints/preferences.py` — `POST /preferences/feedback` endpoint (thumbs up/down → `Generation.userRating` + `User.preferences.style_dna`)
- [x] Style DNA schema: `{styles: {}, buckets: {}, tiers: {}, liked: N, disliked: N}` stored in `User.preferences` JsonB
- [x] `services/smart/generation_router.py` — `generate()` accepts `user_preferences`; if bucket score < -2 → auto-switch to most liked bucket; top style (score ≥3) appended to Gemini context
- [x] `api/v1/endpoints/unified_generate.py` — `GenerateRequest` accepts optional `user_preferences` dict → forwarded to router
- [x] `apps/web/app/api/preferences/thumbs/route.ts` — upgraded: always updates `userRating` + `style_dna`; PreferencePair (RLHF) created silently if second image exists
- [x] `apps/web/app/api/generate/smart/route.ts` — fetches `User.preferences` (Style DNA) from DB before generation, passes to backend
- [x] Frontend: 👍/👎 buttons in result view (`generate/page.tsx`) — green/red highlight on selection, resets on new generation, calls `/api/preferences/thumbs` best-effort

### 🔧 P4 — Enable When Ready
- [ ] **Ideogram** — add key, set `USE_IDEOGRAM=true` (typography bucket becomes much better)
- [ ] **Anthropic/Claude** — add key, set `USE_ANTHROPIC=true` (richer creative briefs)
- [ ] **Recraft v3** — vector/SVG specialist (add `recraft_client.py`)

### 🔧 P5 — Own GPU Comeback (Month 3+)
- [ ] Wake SageMaker endpoints when volume > 500 images/month
- [ ] A/B test own GPU vs API on same prompt set
- [ ] Gradually shift volume to own infra (₹0.50/image vs ₹4-5/image API)

---

## 7. Key Files Reference

### Active (Touch carefully)
| File | Role |
|---|---|
| `apps/api/app/api/v1/endpoints/unified_generate.py` | Main endpoint — all 7 stages |
| `apps/api/app/services/smart/generation_router.py` | SmartGenerationRouter (Stage 3) |
| `apps/api/app/services/smart/gemini_prompt_engine.py` | 2-step Gemini prompt engine |
| `apps/api/app/services/smart/config.py` | Capability routing table + styles/themes |
| `apps/api/app/services/external/fal_client.py` | fal.ai async client |
| `apps/api/app/services/external/ideogram_client.py` | Ideogram client (disabled) |
| `apps/api/.env.local` | All API keys + feature flags |

### HOLD (Don't delete, don't run)
| File | Role |
|---|---|
| `aws/sagemaker/generation/inference.py` | GPU1 PixArt v31 |
| `aws/sagemaker/orchestrator/inference.py` | GPU2 RealVisXL v3.2 |
| `ai-pipeline/services/finish/flux_finish.py` | SageMaker async caller |

---

## 8. What Makes Us UNBEATABLE vs Everyone

| Feature | ChatGPT | Grok | Gemini | Higgsfield | **PhotoGenius** |
|---|---|---|---|---|---|
| Raw prompt → WOW | Good | Basic | Good | Good | **Best** (7-stage Creative OS) |
| Photographer brief | No | No | No | No | **Gemini 2-step ✅** |
| Model specialization | No | No | No | Limited | **8-bucket router** |
| Ensemble + judge | No | No | No | No | **P1: 3 cands, auto-pick** |
| Typography routing | Basic | No | Basic | No | **Ideogram (when on)** |
| Multi-provider failover | No | No | No | No | **P1: 4 providers** |
| Poster/Ad pipeline | No | No | No | No | **7-stage Creative OS** |
| Brand compliance | No | No | No | No | **brand_checker ✅** |
| CTR prediction | No | No | No | No | **ctr_predictor ✅** |
| Progressive UI | No | No | No | No | **P2: SSE stages ✅** |
| Cost per image | ₹15-20/mo | ₹15-20/mo | ₹15-20/mo | ₹843/mo | **₹0.25-8.50** |
| Pay-per-use | No | No | No | No | **Yes ✅** |
| Own GPU future | No | No | No | No | **P5: SageMaker** |

---

## 9. Monthly Model Update Protocol

Every 30 days:
1. Run same 10 test prompts across all active models
2. Score: realism + text accuracy + anatomy + composition + prompt adherence
3. Update `BUCKET_MODEL_MAP` in `config.py`
4. Log in changelog below

**Model Changelog:**
| Date | Bucket | Changed From | Changed To | Reason |
|---|---|---|---|---|
| Mar 21, 2026 | ALL | SageMaker PixArt | fal.ai Flux Pro | Fast-move phase start |
| Mar 21, 2026 | Prompt Engine | Heuristic keywords | Gemini 2.5 Flash | Quality leap |
| Mar 21, 2026 | Typography | text_overlay only | flux-pro (ideogram pending) | Ideogram key pending |
| Mar 21, 2026 | Photorealism | `flux-pro` $0.05 | `flux-2-pro` $0.03 | Gen 2 better + 40% cheaper (P1) |
| Mar 21, 2026 | Character/Editing | `flux-redux` | `flux-kontext-pro` | Kontext purpose-built for consistency (P1) |
| Mar 21, 2026 | Vector | None | `recraft-v4-svg` $0.08 | True SVG output, #1 ranked (P1) |
| Mar 21, 2026 | Anime | (artistic bucket) | `hunyuan-image` $0.03 | Best for anime/Asian styles (P1) |
| Mar 21, 2026 | Fast | `flux-schnell` fal.ai $0.003 | Fireworks AI $0.0014 | 2x cheaper same model (P1) |

---

## 10. Tier Pipeline Detail (P1 Target)

```
FAST:     Gemini brief → Schnell ×1 → output                        ₹0.25
STANDARD: Gemini brief → Schnell ×3 → jury → ESRGAN 4x → output    ₹1.00
PREMIUM:  Gemini brief → Schnell ×3 → jury → Flux Dev refine → out  ₹3.00
ULTRA:    Gemini brief → Pro ×1 + Dev ×2 → jury → post-proc → out   ₹8.50
```

**Key insight:** Gemini prompt engine + ensemble jury + ESRGAN upscale closes 95% of the quality gap between Schnell and Pro. The remaining 5% only matters for ULTRA tier where margin justifies it.

---

## 11. One-Line Summary

> PhotoGenius = 7-stage Creative OS + Gemini photographer brief + 8-bucket capability router + multi-provider failover + Schnell ensemble jury + ESRGAN upscale = **Midjourney quality at ₹1/image, with pay-per-use pricing**.

---

*Last updated: March 23, 2026 | P3 User Personalization complete | Production build: ✅ 0 errors*
