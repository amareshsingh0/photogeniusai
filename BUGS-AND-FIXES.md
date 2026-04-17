# PhotoGenius AI — Bug Log & Fixes

> Every confirmed bug goes here after fix.
> Purpose: agents check this before diagnosing new errors (patterns repeat).
> Format: newest first.

---

## BUG LOG

---

### [2026-04-17] Typography prompts — event-specific auto-fill missing
**Severity**: Medium
**File**: `apps/api/app/services/smart/claude_prompt_engine_v2.py`
**Symptom**: Typography generation didn't auto-fill event-specific context (dates, venue, etc.)
**Root Cause**: Prompt template didn't include event-type detection branch
**Fix**: Enhanced typography prompts with event-specific auto-fill + rich visual examples
**Commit**: `237b65f`
**Pattern**: When adding new prompt logic, always check all bucket-specific branches in `claude_prompt_engine_v2.py`

---

### [2026-04-17] Prisma parallel testing — outputUrls type mismatch
**Severity**: High
**File**: `apps/api/app/api/v1/endpoints/generate_stream.py` → `_generate_with_model()`
**Symptom**: Parallel testing mode crashed on DB write — Prisma schema expects JSON object, code passed array
**Root Cause**: `outputUrls` field is `Json` type in Prisma schema, but code was sending `list[str]`
**Fix**: Changed `outputUrls` from array `[url1, url2]` to JSON object `{"urls": [url1, url2], "model": model_id}`
**Also Fixed**: `userId` was using `DEV_USER` string literal instead of actual UUID from DB
**Commit**: `1caa593`
**Pattern**: Always check Prisma schema type before passing data — `Json` ≠ `list`, `String` ≠ `UUID object`

---

### [2026-04-17] Imagen 4 endpoint — wrong URL format
**Severity**: High
**File**: `apps/api/app/services/external/multi_provider_client.py` → `_call_google()`
**Symptom**: Imagen 4 API calls returning 404
**Root Cause**: Using old endpoint format; correct format is `:predict` suffix
**Fix**: Updated to `imagen-4.0-generate-001` model ID + `:predict` endpoint
**Commit**: `95b7284`, `a2a6594`
**Pattern**: Google Vertex AI endpoints use `:predict` suffix. Verify endpoint format whenever Google updates model IDs.

---

### [2026-04-17] Copy writer truncation — agent max tokens missing
**Severity**: Medium
**File**: `apps/api/app/services/smart/design_agent_chain.py`
**Symptom**: Copy writer fallback path truncated output silently
**Root Cause**: `copy_writer_fallback` key missing from `_AGENT_MAX_TOKENS` dict
**Fix**: Added `"copy_writer_fallback": 2000` to `_AGENT_MAX_TOKENS`
**Pattern**: Every agent codepath (main + fallback) needs an entry in `_AGENT_MAX_TOKENS`. Check both when adding new agents.

---

### [2026-04-15] Resolution tier routing — wrong config source
**Severity**: High
**File**: `apps/api/app/services/smart/generation_router.py`
**Symptom**: Models not routing correctly to resolution tiers
**Root Cause**: Router was reading from `config.py` (old style definitions) instead of `model_config.py` (new BUCKET_MODEL_MAP)
**Fix**: Switched all routing to `model_config.py` → `BUCKET_MODEL_MAP`
**Pattern**: Single source of truth for model routing is `model_config.py`. Never read model assignments from `config.py`.

---

### [2026-04-14] Provider cleanup — extra providers breaking routing
**Severity**: High
**File**: `apps/api/app/services/external/multi_provider_client.py`
**Symptom**: Random routing failures, some model calls going to removed providers
**Root Cause**: 5 removed providers (Fireworks, Together, Replicate, BFL, Kie, Pixazo) still had dead code paths
**Fix**: Full cleanup — only 3 providers remain: fal.ai, Google Vertex, WaveSpeed
**Pattern**: When removing a provider, grep the entire codebase for its name before closing the PR.

---

### [2026-04-10] Hydration error #418/#422 — sessionStorage in useState
**Severity**: Medium
**File**: `apps/web/app/(dashboard)/generate/page.tsx`
**Symptom**: React hydration mismatch error on page load (Next.js SSR vs client)
**Root Cause**: `sessionStorage` access inside `useState()` initial value — runs on server (SSR) where `sessionStorage` doesn't exist
**Fix**: Moved `sessionStorage` access into `useEffect()` (client-only)
**Pattern**: Never access `localStorage`, `sessionStorage`, `window`, or `document` in:
- `useState(initialValue)`
- Component body (top-level)
Always wrap in `useEffect(() => { ... }, [])`.

---

### [2026-04-08] UUID error — DEV_USER.id string vs actual UUID
**Severity**: High
**File**: `apps/web/lib/auth.ts` + `apps/web/app/api/generate/stream/route.ts`
**Symptom**: DB inserts failing with "invalid UUID" Prisma error
**Root Cause**: `DEV_USER.id` was a hardcoded string `"dev-user"` instead of the actual UUID from DB
**Fix**: `DEV_USER.id` → `ee10a6d4-a124-4fea-ac1f-395d4f3adb6c` (actual UUID from users table)
**Pattern**: DEV_USER must always use the real UUID from the DB, not a placeholder string. Check `prisma.user.findUnique({ where: { email: "dev@photogenius.local" } })` if UUID changes.

---

## RECURRING PATTERN INDEX

Quick reference for agents — search here before diagnosing:

| Symptom | Likely Cause | See Bug Entry |
|---------|-------------|---------------|
| Prisma type error on write | Array passed where Json expected | 2026-04-17 Prisma parallel |
| UUID invalid error | DEV_USER string vs real UUID | 2026-04-08 UUID error |
| React hydration mismatch | sessionStorage/localStorage in useState | 2026-04-10 Hydration |
| Model routing to wrong provider | Reading config.py instead of model_config.py | 2026-04-15 Resolution tier |
| Google API 404 | Wrong endpoint format (missing :predict) | 2026-04-17 Imagen 4 |
| Agent output truncated silently | Missing entry in _AGENT_MAX_TOKENS | 2026-04-17 Copy writer |
| Provider call fails randomly | Removed provider still in code path | 2026-04-14 Provider cleanup |

---

## HOW TO ADD A BUG ENTRY

```markdown
### [YYYY-MM-DD] Short description
**Severity**: Low / Medium / High / Critical
**File**: path/to/file.py (line or function if known)
**Symptom**: What the user/system saw
**Root Cause**: Why it happened
**Fix**: What was changed
**Commit**: git commit hash (if available)
**Pattern**: Generalizable lesson for future agents
```
