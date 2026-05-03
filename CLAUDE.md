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
| typography | seedream_4_5 | ideogram_v3 | imagen_4_ultra |
| photorealism | flux_2_flex | gemini_3_imagen | imagen_4_ultra |
| artistic | wan_2_7 | grok_2_imagine | imagen_4_ultra |
| anime | wan_2_7 | wan_2_7 | gemini_3_1_imagen |
| vector | recraft_v4_pro | recraft_v4_pro | recraft_v4_pro |
| fast | seedream_4_5 | flux_2_flex | imagen_4_base |

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

**C. Stage-2.5 critique pass (now via GEMINI)** - Per project rule: Haiku owns prompt enrichment, Gemini owns ALL other LLM steps. The critique pass calls Gemini 2.5 Flash with a 10-point checklist covering all 4 phases of the ad-creator framework. Only fires when `classification.is_ad == True`. Flag: `USE_SELF_CRITIQUE` (default `true`). +$0.0001 / +~1.5s per ad generation. Failure non-fatal (keeps draft).

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
