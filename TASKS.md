# PhotoGenius AI — Agent Task Board

> Shared file between all agent panes (Team Lead, Backend, Frontend, Error Monitor).
> Update this file as you pick up, progress, and complete tasks.
> Format: `- [x]` = done · `- [~]` = in progress · `- [ ]` = todo

---

## ACTIVE SPRINT — Sprint 8: Custom JWT Auth
**Goal**: Replace DEV_USER pattern with real JWT authentication
**Deadline**: TBD
**Lead Agent**: Backend

### Tasks
- [ ] Design JWT token schema (payload: userId, email, role, exp)
- [ ] Create `/api/v1/auth/login` endpoint → returns signed JWT
- [ ] Create `/api/v1/auth/refresh` endpoint → refresh token flow
- [ ] Create JWT middleware for FastAPI (verify on every protected route)
- [ ] Update `apps/web/lib/auth.ts` — replace DEV_USER with JWT decode
- [ ] Update `apps/web/app/api/generate/stream/route.ts` — pass JWT in headers
- [ ] Update SSE pipeline (`generate_stream.py`) — extract userId from JWT
- [ ] Keep DEV_USER as fallback when `NODE_ENV=development`
- [ ] Admin role check: `role === "admin"` instead of email check
- [ ] Add to Admin Panel → Feature Config: `USE_JWT_AUTH` flag

---

## IN PROGRESS
> Agents: move your task here when you start it. Include your pane name.

*(empty — add tasks as you start them)*

---

## ERROR QUEUE
> Error Monitor agent writes here. You approve → Backend/Frontend agent fixes.

*(empty — populated automatically from Sentry)*

---

## FEATURE BACKLOG

### Sprint 3: Canvas Editor
- [ ] Design canvas editor UI (Next.js, Fabric.js or Konva)
- [ ] Drag & drop image layers
- [ ] Text overlay on generated images
- [ ] Export to PNG/JPG
- [ ] Save canvas state to DB (Prisma)

### Sprint 4: Brand Kit
- [ ] Brand profile schema (logo, colors, fonts, tone)
- [ ] Brand Kit creation UI (admin + user)
- [ ] Inject brand context into Master Strategist prompt
- [ ] Brand consistency scoring in quality_critic.py
- [ ] Per-user brand kit storage (Prisma)

### Sprint 5: Batch Generation
- [ ] Batch request schema (array of prompts + settings)
- [ ] Queue system for batch jobs (task_queue.py)
- [ ] Batch results UI — grid view
- [ ] Progress SSE stream for batch status
- [ ] Cost estimation before batch runs

### Sprint 6: Advanced Auth (post-JWT)
- [ ] User registration flow
- [ ] Password reset
- [ ] Email verification
- [ ] Role management UI in Admin Panel

### Ongoing Improvements
- [ ] Add Sentry error tracking to FastAPI (`pip install sentry-sdk[fastapi]`)
- [ ] Add Sentry to Next.js (`pnpm add @sentry/nextjs`)
- [ ] Cache hit rate logging in design_agent_chain.py
- [ ] Semantic judge upgrade (binary/categorical scoring, temperature=0)
- [ ] ModernBERT complexity classifier for predictive routing
- [ ] GitHub Actions CI/CD pipeline (`.github/workflows/ci.yml`)

---

## COMPLETED

### 2026-04-17
- [x] BEAST Phase 2: Master Strategist (58% faster, 60% token savings)
- [x] BEAST Phase 3: Deterministic Layout (CV-based, 100% reliable)
- [x] BEAST Phase 4: Hybrid Quality Critic (VLM + Python, 95% accuracy)
- [x] Switch from config.py to model_config.py BUCKET_MODEL_MAP
- [x] Resolution tiers: 1K/2K/4K (backward-compatible via normalize_quality_tier)
- [x] 3-provider cleanup (removed Fireworks, Together, Replicate, BFL, Kie, Pixazo)
- [x] WaveSpeed integration (Grok 2, Wan 2.7, Hunyuan)
- [x] Prisma parallel testing fixes (userId UUID + outputUrls JSON)
- [x] Imagen 4 endpoint update (imagen-4.0-generate-001)
- [x] Typography prompts: event-specific auto-fill + rich visual examples
- [x] Hydration fix (#418/#422): sessionStorage moved to useEffect
- [x] Copy writer truncation fix (copy_writer_fallback in _AGENT_MAX_TOKENS)

---

## AGENT COORDINATION PROTOCOL

```
1. Pick a task from backlog → move to IN PROGRESS with your pane name
2. Implement → test locally
3. Write what you did in COMPLETED with date
4. If you find a bug, add it to ERRORS.md (not here)
5. If blocked, write [BLOCKED: reason] next to the task
6. Never work on the same file as another agent simultaneously
```

---

## FILE OWNERSHIP (prevent conflicts)

| Area | Agent |
|------|-------|
| `apps/api/app/services/smart/` | Backend Agent |
| `apps/api/app/services/external/` | Backend Agent |
| `apps/api/app/api/v1/endpoints/` | Backend Agent |
| `apps/web/app/(dashboard)/` | Frontend Agent |
| `apps/web/app/admin/` | Frontend Agent |
| `apps/web/app/api/` | Frontend Agent (consult Backend) |
| `apps/web/lib/` | Frontend Agent |
| `TASKS.md` / `ERRORS.md` | All agents |
