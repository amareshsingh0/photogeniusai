# Pixium AI — Claude Code Agent Memory

> Read this file completely before touching any code.
> This is the single source of truth for all agents.

---

## IDENTITY

**Product**: Pixium AI — AI image generation platform for creatives
**API**: `api.creatives.bimoraai.com` (FastAPI, port 8003, PM2)
**Web**: `creatives.bimoraai.com` (Next.js 14, port 3002, PM2)
**Admin**: `api.creatives.bimoraai.com/admin`
**Server**: `ssh -i "C:\desktop\PhotoGenius AI\bimoraAI.pem" ubuntu@43.204.223.51`

---

## ABSOLUTE RULES — NEVER BREAK THESE

1. **Package manager: pnpm ONLY** — never npm, never yarn, never bun
2. **Prisma for ALL DB operations** — never raw SQL, never direct Supabase client in Python API
3. **Never commit `.env` files** — secrets in `.env.local` or server environment only
4. **Never change the 3-provider stack** — fal.ai · Google Vertex · WaveSpeed only
5. **Never add a 4th provider** — Fireworks, Together, Replicate, BFL are REMOVED on purpose
6. **Prompt caching: static system prompts BEFORE dynamic user input** — always
7. **Resolution tiers: 1K / 2K / 4K ONLY** — legacy names (fast/balanced/quality/ultra) map via `normalize_quality_tier()`
8. **Feature flags go in Admin Panel → Feature Config tab** — not hardcoded booleans
9. **Admin user**: `dev@photogenius.local` / UUID: `ee10a6d4-a124-4fea-ac1f-395d4f3adb6c`
10. **Deploy sequence**: `git pull → pnpm build --filter=web → pm2 restart all`

---

## STACK

| Layer | Technology |
|-------|-----------|
| Monorepo | Turborepo + pnpm workspaces |
| Frontend | Next.js 14 · TypeScript · Tailwind CSS · shadcn/ui |
| Backend | FastAPI (Python 3.11) |
| Database | Prisma ORM → Supabase PostgreSQL |
| Auth | DEV_USER pattern (Clerk removed; JWT pending Sprint 8) |
| Process | PM2 (both web + api) |
| AI — Prompt Engine | Claude Haiku 4.5 (extended thinking for briefs, standard for params) |
| AI — Copy Writer | Gemini 2.5 Flash |
| AI — Quality Judge | Gemini Vision (12 dims) |

---

## 3-PROVIDER MODEL STACK

### Provider 1: fal.ai (Primary Aggregator)
- **Models**: Flux 2 Flex · Ideogram v3 · Recraft v4 Pro/SVG · Seedream 4.5 · Real-ESRGAN
- **Client function**: `multi_provider_client.py` → `_call_fal()`
- **Key**: `FAL_KEY`
- **Cost**: $0.015–$0.055 per image (cheapest)

### Provider 2: Google Vertex AI
- **Models**: Gemini 3 Imagen · Gemini 3.1 Imagen · Imagen 4 Base/Fast/Ultra
- **Client function**: `multi_provider_client.py` → `_call_google()`
- **Key**: `GEMINI_API_KEY` (3 keys, round-robin)
- **Best for**: Enterprise photoreal, 4K resolution, Imagen 4 Ultra = 9.2/10 quality

### Provider 3: WaveSpeed (Aggregator)
- **Models**: Grok 2 Imagine (X.ai) · Wan 2.7 · Hunyuan Image (Tencent)
- **Client function**: `multi_provider_client.py` → `_call_wavespeed()`
- **Key**: `WAVESPEED_API_KEY`
- **Best for**: Creative/uncensored styles, Asian aesthetics, Chinese text

### Resolution Routing (BUCKET_MODEL_MAP in model_config.py)
| Bucket | 1K | 2K | 4K |
|--------|----|----|-----|
| typography | gpt_image_2 | gpt_image_2 | gpt_image_2 |
| photorealism | flux_2_flex | imagen_4_base | imagen_4_ultra |
| artistic | grok_2_imagine | gemini_3_1_imagen | imagen_4_ultra |
| anime | wan_2_7 | gemini_3_1_imagen | imagen_4_ultra |
| vector | recraft_v4_pro | recraft_v4_pro | imagen_4_ultra |
| vector (admin testing) | recraft_v4_pro + recraft_v4_svg + gpt_image_2 | recraft_v4_pro + gpt_image_2 | gpt_image_2 |
| fast | seedream_4_5 | gemini_3_imagen | imagen_4_ultra |

**Reference-image / edit path**: ALL edit modes (instruction_edit, compose, style_remix, inpaint_mask, object_add/remove, background_swap, text_replace) prefer `gpt_image_2_edit` first. Tier hard-clamped to 1K when reference image present.

---

## 4-AGENT PIPELINE

```
USER PROMPT
    ↓
Intent Analyzer (Python) + Bucket Detection (config.py → detect_capability_bucket)
    ↓
[Typography bucket] → 4-Agent Chain (design_agent_chain.py):
    1. Master Strategist — Claude Haiku 4.5 (extended thinking) — consolidates Triage+Brand+CD
    2. Copy Writer — Gemini 2.5 Flash — parallel Best-of-N drafts
    3. Image Prompter — Gemini 2.5 Flash ─┐ run in parallel
    4. Layout Planner — Gemini 2.5 Flash ──┘
    ↓
[Other buckets] → Claude Prompt Engine v2 (claude_prompt_engine_v2.py):
    Stage A: Claude Sonnet 4.6 → Creative Brief JSON
    Stage B: Claude Haiku 4.5 → Generation Params JSON
    Validator: schema + budget + bucket-rule check
    ↓
Multi-Provider Generation (multi_provider_client.py — cheapest-first routing)
    ↓
Quality Gate (quality_critic.py — Gemini Vision, 12 dims + 10 Beast gates)
    ↓
FINAL IMAGE → SSE stream to frontend
```

---

## KEY FILE LOCATIONS

### Python API (`apps/api/app/`)
| File | Purpose |
|------|---------|
| `services/external/multi_provider_client.py` | 3-provider client (fal, Google, WaveSpeed) |
| `services/smart/model_config.py` | Model registry (10 models) + BUCKET_MODEL_MAP |
| `services/smart/config.py` | Central config — typography, styles, bucket detection |
| `services/smart/design_agent_chain.py` | 4-agent typography chain (2690 lines) |
| `services/smart/master_strategist.py` | Unified Master Strategist (1400+ lines) |
| `services/smart/claude_prompt_engine_v2.py` | Claude prompt engine (Stage A/B/Validator) |
| `services/smart/quality_critic.py` | 12-dim quality scorer |
| `services/smart/generation_router.py` | Generation routing logic |
| `services/smart/beast_router_2026.py` | BEAST routing (2026 architecture) |
| `services/smart/smart_cache.py` | Smart caching layer |
| `api/v1/endpoints/generate_stream.py` | SSE pipeline + parallel testing mode |
| `api/v1/endpoints/admin.py` | Admin endpoints |
| `api/v1/endpoints/admin_config.py` | Feature flag endpoints |

### Next.js Web (`apps/web/`)
| File | Purpose |
|------|---------|
| `app/(dashboard)/generate/page.tsx` | Main generate page |
| `app/api/generate/stream/route.ts` | SSE proxy + DB save |
| `app/admin/page.tsx` | Admin dashboard (6 tabs) |
| `lib/auth.ts` | DEV_USER (UUID: ee10a6d4-a124-4fea-ac1f-395d4f3adb6c) |

---

## FEATURE FLAGS (Admin Panel → Feature Config)

```
USE_MASTER_STRATEGIST=true       — 4-agent chain for typography
USE_CLAUDE_ENGINE=true           — Claude prompt engine (vs heuristic)
USE_IDEOGRAM=false               — Ideogram direct (disabled)
USE_DETERMINISTIC_LAYOUT=false   — CV-based layout planner
USE_HYBRID_QUALITY_CRITIC=false  — VLM + Python gates
USE_PROMPT_CACHING=true          — Anthropic prefix caching
USE_SMART_CACHE=true             — Smart response cache
USE_LLMLINGUA_COMPRESSION=true   — Prompt compression
```

---

## BEAST ARCHITECTURE (All 4 Phases Complete)
- **Phase 2**: Master Strategist — 58% faster, 60% token savings
- **Phase 3**: Deterministic Layout — CV-based, 100% reliable
- **Phase 4**: Hybrid Quality Critic — VLM + Python gates, 95% accuracy

---

## ADMIN PANEL (6 Tabs)
`Overview` | `Users` | `Generations` | `Models` | `Feature Config (16 flags)` | `Settings (auto-restart)`

**Parallel Testing Mode**: Admin user sees multi-model results grid. Normal users see single result. Zero UI changes for normal users.

### Admin Model Control Flow (canonical)
1. **Source of truth**: `apps/api/app/api/v1/endpoints/admin_models.py` → `DEFAULT_MODELS` list. Each entry has `modelId`, `buckets[]`, `isActive`, `isTestingEnabled`, `costPerImage`.
2. **Seed DB**: `POST /api/v1/admin/models/seed` reads DEFAULT_MODELS and upserts into Prisma `ModelConfig` table.
3. **Runtime override**: Admin Panel → Models tab can flip `isActive`/`isTestingEnabled` per model live (no redeploy).
4. **Generate-time routing**:
   - Bucket detected via `classify_intent()` (Gemini 2.5 Flash).
   - DB query: `isActive=true AND isTestingEnabled=true AND bucket IN buckets[]`.
   - **Admin (`testing_mode=true`)**: all matched models run in parallel → results grid.
   - **Normal user**: picker chooses one (cheapest matched) → single result.
   - **DB-empty fallback**: when query returns 0, build synthetic ModelConfig entries from DEFAULT_MODELS for that bucket so parallel still works (added May 5 2026).
5. **Adding a model to a bucket**: edit `DEFAULT_MODELS[i]["buckets"]` list, redeploy, run seed endpoint OR toggle in Models tab. Both paths converge on the same DB row.

---

## AUTHENTICATION
- Clerk: **REMOVED**
- DEV_USER pattern: currently active
- Custom JWT: **pending Sprint 8**
- Admin check: `email === "dev@photogenius.local"`

---

## KNOWN WORKING PATTERNS

### Correct: DB operation
```python
# Always Prisma, never raw Supabase client
user = await prisma.user.find_unique(where={"email": email})
```

### Correct: Adding a feature flag
```python
# In config.py or env
USE_NEW_FEATURE = os.getenv("USE_NEW_FEATURE", "false").lower() == "true"
# Then expose in admin_config.py endpoint
```

### Correct: Prompt caching structure
```python
messages = [
    {"role": "user", "content": [
        {"type": "text", "text": STATIC_SYSTEM_PROMPT, "cache_control": {"type": "ephemeral"}},
        {"type": "text", "text": f"User input: {dynamic_user_input}"}
    ]}
]
```

### Correct: Resolution tier
```python
from app.services.smart.model_config import normalize_quality_tier
tier = normalize_quality_tier(user_input_tier)  # Always normalizes to 1k/2k/4k
```

---

## TWO-STAGE INTENT ROUTING (May 3 2026)

Replaces the old keyword-based `detect_capability_bucket` + alias-based `_match_recipe`. Pure AI-driven now:

```
USER PROMPT
   v
[Stage 1] Gemini 2.5 Flash classifier  ->  {bucket, category_key, has_text, is_ad, platform}
   v
[Recipe lookup] direct key match in category_recipes JSON (no alias substring scan)
   v
[Stage 2] Haiku 4.5 enrichment with recipe pre-injected into user message
   v
Per-model formatter (GPT/Imagen/Wan/Flux dialects)
   v
IMAGE MODEL
```

**Files / functions** (in `simple_prompt_engine.py`):
- `classify_intent(user_prompt)` -> async, per-process cached. Used by both `generate_stream.py` (for bucket routing) and `enrich()` (for recipe lookup) - one Gemini call total per generation.
- `_classify_intent_gemini` -> the actual Gemini call, JSON-validated output, safe fallback on error.
- `_recipe_by_key(category_key)` -> direct dict lookup in `category_recipes_mined.json` + `category_recipes.json`.
- `_match_recipe` -> REMOVED (alias substring matching deleted).

**Files** (`apps/api/app/services/smart/data/`):
- `category_recipes.json` - manual entries for verticals Pitt taxonomy misses (ayurveda, packaging, wedding, dental, salon, etc.)
- `category_recipes_mined.json` - auto-generated from Pitt Image Ads (CVPR 2017, 64K real ads, 38 industry topics) + PeterBrendan AdCopy programmatic dataset.

**Caching**: `_CLASSIFICATION_CACHE` (256-entry LRU-ish) keys on the user prompt string. Re-using `classify_intent` within a single request costs nothing.

**Cost / latency**: ~$0.0001 per generation, ~300ms (Gemini 2.5 Flash, 150 input + 60 output tokens).

**Bucket detection in `generate_stream.py`**: All 4 call sites of `detect_capability_bucket` are now wrapped in `await classify_intent(prompt)` first - keyword detection is the fallback only.

---

## AD QUALITY UPGRADES (May 3 2026)

Five gap-closing improvements deployed together to narrow the gap with ChatGPT/Gemini's native ad outputs:

**A. Negative-space directives in every formatter** - GPT formatter has explicit `NEGATIVE SPACE:` bullet, Imagen formatter adds a dedicated copy-space sentence, Flux + Wan AD-mode formatters bake "clean uncluttered area on one side of the frame" into the prompt.

**B. Pydantic hard caps on text lengths** - `headline` max 40 chars (2-5 words), `subhead` max 80 (5-10), `cta` max 25 (2-3). Previously 200/400/120. Forces Nike-level brevity at the schema layer.

**D. Flux + Wan formatters rewritten** - Both used to be near-passthroughs of Haiku output. Now they construct AD-mode prompts from `simple_payload` structured fields, with research-grade templates: Flux gets 85mm camera physics + negative-space + max 4 short text strings. Wan gets `/imagine prompt:`-style scene narrative + max 1 short headline (Wan can't render longer text reliably). Both keep SCENE-mode passthrough for non-ad prompts.

**E. Background-behind-text clauses** - Each text-element bullet in GPT formatter now ends with "background DIRECTLY behind these letters must be a clean uncluttered surface". Same idea woven into Imagen's negative-space sentence.

**C. Stage-2.5 critique pass (now via GEMINI)** - Per project rule: Haiku owns prompt enrichment, Gemini owns ALL other LLM steps. The critique pass calls Gemini 2.5 Flash with a 16-point checklist (May 4 expansion) covering all 5 phases of the ad-creator framework + 6 hard anti-patterns + 0.3-second test. Only fires when `classification.is_ad == True`. Flag: `USE_SELF_CRITIQUE` (default `true`). +$0.0001 / +~1.5s per ad generation. Failure non-fatal (keeps draft).

---

## 5-PHASE AD CREATOR BRAIN v2 (May 4 2026 - full research-backed expansion)

Expanded from May 3's 4-phase framework after deep dive into 4 new research docs. Added a brand-new **Phase 0** + expanded Phase 2 + new Phase 5. Now 5 phases:

**PHASE 0 - ROOT-CAUSE + CONCEPT** (the FIRST thing the model does)
- **Master Sentence**: "This ad makes [audience] feel [emotion] so they [action]" - filled BEFORE any visual decision.
- **5 Whys** root-cause analysis - drill past surface request to find real strategic need.
- **Visual Metaphor** (`visual.visual_metaphor` new field) - the CONCEPT that makes the ad memorable. Examples: "shoe in mid-air being struck by water that beads off cleanly" / "bottle on weathered ship deck, sunset over deep navy ocean". Single biggest gap between AI slop and real ads.
- **Micro-Details** (`visual.micro_details` new list field) - 0-5 concrete textural specifics ("icy condensation drops", "embossed gold foil", "wet wood grain"). Replace generic adjectives.
- **Pain vs Desire** mapping - sells the solution to a pain OR the promise of a desired state, NEVER the product.
- **Buyer Behavior Type** - impulse / research / habit / aspirational - calibrates ad structure.
- **Audience Persona Library** - Gen Z / Millennial / Gen X / Boomer hardwired visual languages.

**PHASE 1 - STRATEGY** (audience + objective + platform - existing, retained)

**PHASE 2 - VISUAL PSYCHOLOGY** (expanded May 4)
- **Atmospheric Mood Map** - 6+ strategic moods (Luxury, Urgency, Minimalism, Futuristic, Warmth, Corporate Authority, Raw Excitement, Aggressive Marketing, Dark Aesthetic, Emotional Storytelling) each with industries + core trigger + visual cues.
- **60-30-10 RULE** explicit format: dominant 60% + secondary 30% + accent 10% (CTA only). The 10% is the highest-contrast hue.
- **Industry Chromatic Logic** - hardwired per-industry color conventions (food fast = ketchup-mustard, finance = blue, luxury = matte black + champagne gold).
- **Color Psychology Map** - 11 base colors with emotion + example brands.
- **Typography MAX 2 fonts rule** + font personality map (serif=heritage, sans=modern, slab=editorial, script=elegant, mono=technical).
- **Per-element typography** (NEW: `ad_copy.headline_typography` / `subhead_typography` / `cta_typography`) - explicit `font: <family> | weight: ... | size: ... | color: ... | tracking: ...` format.
- **Visual Hierarchy** (Z-pattern / F-pattern / center-out) + Rule of Thirds intersection.

**PHASE 3 - COMPOSITION** (existing - 35%+ negative space, clean bg behind text, Rule of Thirds)

**PHASE 4 - COPYWRITING & ACTION** (expanded May 4)
- **Hook architecture** + Rule of Three + THUMB TEST.
- **CTA as Call-to-Value** (research-backed +32% CTR) - "Buy Now" -> "Start Saving Today".
- **Loss aversion headline** (+18% conversion lift) - "Don't miss" beats "Save".
- **Persuasion Bias Library** - bake ONE bias into the visual: Scarcity / Social Proof / Authority / Anchoring / Reciprocity.
- **Legal Disclaimer** (NEW: `ad_copy.legal_disclaimer`) - mandatory for alcohol/tobacco/pharma/financial/gambling. Renders on a thin dark band at bottom edge.

**PHASE 5 - UNIVERSAL DISCIPLINES** (NEW May 4)
- **Singularity Principle** - what is the ONE thing this ad communicates?
- **Working memory limit** - max 3 primary focal points (each gets ~33% attention).
- **Directional Element Rule** (research-backed +25% engagement) - all gazes/arrows/motion point TOWARD headline+CTA.
- **Ethics**: no false urgency, no misleading visuals, no greenwashing, WCAG 4.5:1 contrast, cultural sensitivity.
- **Contrast Thinking** - if every category competitor does X, do the OPPOSITE (Economist red-on-white).
- **0.3-second test** - in 0.3s would viewer recognize brand + understand offer + know next step?

## SCHEMA fields added May 4

| Field | Type | Purpose |
|---|---|---|
| `visual.visual_metaphor` | str (≤300) | The CONCEPT - what makes this ad memorable |
| `visual.micro_details` | list[str] (0-5) | Concrete textural specifics |
| `ad_copy.headline_typography` | str (≤200) | Per-element font/weight/size/color/tracking |
| `ad_copy.subhead_typography` | str (≤200) | Per-element styling |
| `ad_copy.cta_typography` | str (≤200) | Per-element styling |
| `ad_copy.legal_disclaimer` | str (≤200) | Regulated industry compliance text |

All threaded through GPT, Imagen, Flux, Wan formatters in `model_prompt_formatter.py`.

---

## 4-PHASE AD CREATOR BRAIN (May 3 2026)

The full ad-creator mental model now baked into the system prompt + schema + formatters + critique. Every ad walks through 4 phases - skipping any phase produces "AI slop" (technically valid, emotionally empty).

**PHASE 1 - STRATEGY** (decisions made BEFORE any visual choice)
- `target_audience` (new field) - specific demographic + psychographic. Examples: "Gen-Z teens 16-22, mobile-first, trend-driven", "Corporate executives 35-55, B2B buyers".
- `objective` (new field) - one of awareness | conversion | engagement | education | retention. Drives EVERY visual choice (conversion -> CTA dominant; awareness -> brand mark + emotional hook dominate; etc).
- `platform` (existing) - dictates aspect ratio + safe zones via PLATFORM_SPECS.

**PHASE 2 - VISUAL PSYCHOLOGY** (why each design choice)
- `color_psychology_intent` (new field) - WHY these colors were chosen ('trust + professionalism', 'urgency + appetite', 'luxury + exclusivity'). Never empty for ads.
- Color map in system prompt: red=urgency/hunger, blue=trust/B2B, green=eco/wealth, black+gold=luxury, etc.
- `typography_style` (tightened) - format `display: <font> / body: <font>`. MAX 2 fonts total (1 display + 1 body). Mixing 3+ = amateur.
- `visual_hierarchy` (new field) - Z-pattern | F-pattern | center-out, named with element positions. Hero placed on Rule-of-Thirds intersection (NEVER dead-center for non-minimalist).

**PHASE 3 - COMPOSITION** (already enforced)
- 35%+ negative space reservation in every formatter
- Clean background DIRECTLY behind quoted text strings
- Rule of Thirds explicit in hierarchy field

**PHASE 4 - COPYWRITING** (already enforced)
- Headline 2-5 words MAX (Pydantic + system prompt + critique)
- Pass the THUMB TEST (would a user STOP at 200ms?)
- CTA 2-3 words, action verb, mandatory for conversion objective

## LLM ROLE SPLIT (May 3 2026 - project rule)

| Stage | Model | Purpose |
|---|---|---|
| 1. Intent classification | Gemini 2.5 Flash | bucket + category_key + has_text + is_ad + platform |
| 2. Prompt enrichment | Claude Haiku 4.5 | structured ad brief generation (the ONLY Haiku call) |
| 2.5. Critique pass | Gemini 2.5 Flash | 10-point ad-creator checklist review of Haiku draft |
| 3. Per-model formatting | (deterministic Python) | model dialect translation |

Rule: Haiku owns prompt enrichment ONLY. Every other LLM step (classification, critique, future review/judging tasks) uses Gemini.

---

## CATEGORY -> PRODUCT NOUN MAP (May 4 2026 visual regression fix)

`model_prompt_formatter.py:_CATEGORY_PRODUCT_NOUN` translates abstract category keys to concrete photograph-able nouns. Used by Imagen, Flux, Wan formatters to lead the prompt with a noun the diffusion model can lock onto.

**Why this exists**: Imagen + Wan have no inherent knowledge of "alcohol_beverage" or "beauty_cosmetics". The earlier formatters fed `f"{cat_clean} product"` → models rendered chocolate balls instead of alcohol bottles (May 4 visual regression).

**Fix**: 60+ entry map covering Pitt-mined + manual recipe categories. Examples:
- `alcohol_beverage` -> "premium dark glass spirit bottle with elegant label"
- `beauty_cosmetics` -> "luxury cosmetic compact or bottle"
- `pet_care` -> "pet food package"
- `medical_pharma` -> "medical product packaging"

Helper: `_product_noun(subject_category, brand)` returns the curated noun, falls back to `f"premium {category} product"` for unmapped keys.

**Imagen subhead cap (May 4)**: `_format_for_imagen` now drops subhead when >4 words — Imagen mangled "Premium Spirits, Uncompromising Taste" as "Unconsprioming" because of length-mangled spelling. Headline + tagline + CTA still carry the message.

**Wan formatter (May 4 regression fix)**: Reverted from 1100-char narrative back to TERSE product-noun-first prompt (Wan parser locks on first concrete noun; long narrative buried the product noun and triggered wrong-subject generation).

**Regenerate mined data** (run on server where datasets live):
```bash
cd ~/PhotoGenius-AI/apps/api && source venv/bin/activate
python3 scripts/mine_category_recipes.py   # writes category_recipes_mined.json
# then scp file back to local repo, commit, deploy
```

**Datasets on server** (`~/PhotoGenius-AI/datasets/`, ~30MB):
- `pitt-ads-text/image/` — Pitt annotations (Topics, Slogans, QA_Action, Sentiments, Strategies)
- `ad-copy/` — PeterBrendan/Ads_Creative_Ad_Copy_Programmatic CSV
- `marketing-social/` — RafaM97 marketing brief examples

---

## LOGO COGNITIVE FRAMEWORK (May 6 2026)

`_BUCKET_HINTS["vector"]` in `simple_prompt_engine.py` is now a 7-phase cognitive framework based on `Research/Logo Design Process and Trends.docx`:

1. **Strategic Diagnosis** — pick a Jungian brand archetype (Caregiver, Ruler, Hero, Explorer, Lover, Outlaw) BEFORE any visual decision
2. **Cognitive-Ease Processing Order** — brain processes color → form → motion → meaning (50ms judgment); 2026 has moved away from washed-out beige toward confident high-contrast
3. **Shape Psychology** — 6 shape families with inherent meanings + tactile materiality (controlled imperfections to escape AI-default polish)
4. **Mark Type Decision** — wordmark / lettermark / pictorial / abstract / combination / emblem-stamp, each with real-world examples
5. **Hyper-Expressive Typography** — explicit anti-blanding mandate, 7 typeface personalities, micro-detail anchors (ink traps, missing notches) as ownership signals
6. **Technical + Accessibility** — 16px → billboard scalability, B&W-first silhouette, ≥25% negative space, WCAG 4.5:1 contrast
7. **Anti-Patterns** — explicit `negative_prompt` directives including "AI-default geometric P/A/B in cyan-and-black", "blanded safe sans-serif", "friction-free synthetic AI polish"

**Anti-Defaults rule**: when brand name suggests literal interpretation (Pixium → pixels), Haiku must push to second/third interpretation. Strong logos earn meaning through unexpected association.

**2026 Trend Checklist**: tactile materiality, stamp/seal, storybook gothic, strategic saturation, micro-detail anchors, retro-futurism, atmospheric gradient — cap at 2 trends to preserve cognitive ease.

Other buckets (photorealism, photorealism_portrait/humans, photorealism_product, artistic, anime) received parallel discipline-rich blocks on May 5 2026 — see Multi-Reference section below.

---

## MULTI-REFERENCE + GPT IMAGE 2 EDIT (May 5 2026)

Generate page now supports up to **5 reference images** (was 1). UI: `+` button with badge showing count, gallery thumbnails, individual X-to-remove + "Clear all".

**Wire path**: `referenceImages[0]` → `reference_image` (primary) | `referenceImages.slice(1)` → `extra_reference_images` → backend `extra_image_urls`.

**GPT Image 2 owns reference-image generation:**
- `_pick_img2img_model` returns `gpt_image_2_edit` unconditionally — Flux Kontext deprecated for refs.
- `_EDIT_MODE_PREFERENCE` (model_config.py) lists `gpt_image_2_edit` FIRST for every edit mode (instruction_edit, compose, style_remix, inpaint_mask, object_add/remove, background_swap, text_replace).
- `_call_openai_edit` sends repeated `image[]` form parts (primary + up to 14 extras) per OpenAI `/v1/images/edits` spec — multi-image compose now works.
- `extra_image_urls` plumbed through 3 generate paths that were silently dropping it (main, quality-retry, parallel `_generate_with_model`).

**Tier auto-clamp**: when `req.reference_image_url` set, tier is hard-clamped to 1K (GPT Image 2 edit only supports 1K reliably).

**SSE heartbeats**: img2img single-model fallback path wraps `_generate_with_model` in 15s heartbeat loop. GPT Image 2 edit takes 60s+ and nginx `proxy_read_timeout=60s` was killing connections silently → "network error" toast.

**Bucket DB-empty fallback** (`_parallel_model_stream`): when admin DB has no models tagged for a bucket (e.g. fresh deploy + vector bucket), build synthetic ModelConfig entries from `admin_models.DEFAULT_MODELS` for that bucket so parallel testing still works (preserves admin's multi-model grid UX). Single-model fallback was the wrong approach. Run `POST /api/v1/admin/models/seed` to seed DB and skip fallback.

---

## SPRINT STATUS (as of 2026-04-17)

| Sprint | Feature | Status |
|--------|---------|--------|
| Sprint 8 | Custom JWT Auth | IN PROGRESS |
| Sprint 3 | Canvas Editor | BACKLOG |
| Sprint 4 | Brand Kit | BACKLOG |
| Sprint 5 | Batch Generation | BACKLOG |
| Sprint 6 | Advanced Auth | BACKLOG |

---

## DEPLOY COMMANDS

```bash
# SSH to server
ssh -i "C:\desktop\PhotoGenius AI\bimoraAI.pem" ubuntu@43.204.223.51

# Full deploy
git pull origin main
pnpm install --frozen-lockfile
pnpm build --filter=web
pm2 restart all
pm2 save

# Check logs
pm2 logs photogenius-api --lines 100
pm2 logs photogenius-web --lines 50
pm2 status

# Python API only
cd apps/api && source venv/bin/activate
pm2 restart photogenius-api
```
