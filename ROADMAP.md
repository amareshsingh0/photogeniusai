# PhotoGenius AI — Product Roadmap

## Phase 4: Poster Quality & Editor (Current Sprint)

### P4.1 — Hero Image Fix ✅ DONE
- Gemini typography prompt → REALISTIC scene direction
- Ideogram Stage B → scene-only, no text in image
- PosterCompositor card height fix (0.18 → 0.26)
- Model label fix (ideogram_quality → "Ideogram v3 Quality")

### P4.2 — Poster Inline Editor
After generation, user can edit poster WITHOUT re-generating:
- Click headline → edit text inline
- Change accent color → live recomposite
- Swap CTA text
- Re-render button → PosterCompositor reruns with new ad_copy
- Backend: POST /api/v1/poster/recompose (takes ad_copy + hero_url → returns new poster)
- Frontend: Overlay editor on poster result with editable zones

### P4.3 — One-Click Aspect Ratio Pack
Single generate → auto-resize to 4 formats:
- 1:1 (Instagram post)
- 9:16 (Instagram Story / Reels)
- 16:9 (YouTube thumbnail / LinkedIn)
- 4:5 (Instagram feed)
- PosterCompositor reflows layout per ratio (no re-generation cost)
- Frontend: "Download Pack" button → zip with all 4 sizes
- Free = 1:1 only, Pro = all 4

### P4.4 — Brand Kit
User saves their brand once, auto-applied to every poster:
- brand_name, logo (upload), primary_color, secondary_color, font_style, tagline
- Stored in DB: User.brand_kit (JSON)
- Auto-injected into Gemini brief for typography bucket
- Frontend: /settings/brand-kit page

### P4.5 — Template Library
10-15 pre-built poster templates:
- Categories: SaaS Launch, Festival Sale, Food & Restaurant, Fashion, Fitness, Real Estate
- User picks template → fills brand name + headline → generates
- Templates = pre-filled Gemini prompts with locked poster_design params
- Frontend: Template picker modal before generation

---

## Phase 5: Interactive Canvas Editor

### P5.1 — Layer-Based Poster Editor (Fabric.js)
Replace flat JPEG output with editable canvas:
- Poster stored as JSON layers: { background_url, headline, subheadline, features[], cta, colors }
- Fabric.js canvas in frontend renders layers
- User can: move elements, resize, change font, change color, replace background
- Export: renders canvas to PNG/JPEG for download
- Stack: Fabric.js (browser canvas) + poster JSON schema in DB

### P5.2 — Background Swap
Replace hero image without changing text layout:
- "Regenerate background" button → calls Ideogram with same brief
- New hero composited into existing layer JSON
- Zero cost for text/layout changes

### P5.3 — Font Library
10-20 Google Fonts available in editor:
- Bold display fonts: Bebas Neue, Anton, Oswald, Black Han Sans
- Elegant serif: Playfair Display, Cormorant
- Clean sans: Inter, DM Sans, Plus Jakarta Sans
- Font picker in layer editor

---

## Phase 6: Multi-Agent System

### P6.1 — Brand Research Agent
Given a website URL or Instagram handle:
- Scrape: logo, primary colors, font style, brand tone
- Auto-fill brand_kit
- Stack: httpx + BeautifulSoup + color extraction (colorthief)

### P6.2 — Triage Agent
Routes user query to correct pipeline:
- "Make a poster" → Design pipeline
- "Edit my image" → Kontext pipeline  
- "Add logo" → Canvas overlay
- "Resize this" → Aspect ratio pack
- Stack: Gemini function calling / tool use

### P6.3 — Iterative Design Agent
Conversation-style poster editing:
- User: "make headline bigger"
- Agent: updates layer JSON, re-renders, shows new version
- User: "change background to blue"  
- Agent: re-generates only background, preserves text layers
- Stack: Gemini with conversation history + layer JSON state

### P6.4 — LangSmith Observability
Full tracing of agent decisions:
- Which agent handled the request
- What tools were called
- Latency per step
- Cost per generation

---

## Phase 7: Platform Features

### P7.1 — Gallery & History
- All generated images saved with prompt + settings
- Filter by: date, mode, bucket, model
- Re-generate from history with same settings

### P7.2 — Team Workspace
- Multiple users under one brand
- Shared brand kit
- Generation history visible to team

### P7.3 — Scheduler & Publishing
- Schedule poster for Instagram/LinkedIn post
- Direct publish via Meta API / LinkedIn API
- Calendar view of scheduled posts

### P7.4 — A/B Testing
- Generate 2 poster variants (different headline/color)
- CTR prediction score for each
- Pick winner

---

## Phase 8: Own GPU Comeback

### P8.1 — SageMaker Revival (500+ images/month threshold)
- GPU 1 (A10G): PixArt-Sigma v31 + CLIP jury
- GPU 2 (A10G): RealVisXL post-processor v3.2
- PREMIUM tier: Two-pass pipeline (GPU1 draft → GPU2 texture refine)
- Cost: ~$0.008/image vs fal.ai $0.04/image → 5x cheaper at scale

---

## Tech Debt / Fixes

- [ ] Custom auth (Clerk removed, own auth needed)
- [ ] Next.js upgrade (14 → 15, security patch)
- [ ] pnpm lockfile compatibility (8.x → 10.x)
- [ ] Gemini creative amplifier temperature tuning
- [ ] Poster hero image — abstract art prevention (P4.1 partial fix)

---

## Priority Order (Next 30 Days)

1. P4.1 ✅ Hero image fix
2. P4.3 — Aspect ratio pack (high user value, low effort)
3. P4.2 — Poster inline editor (differentiator)
4. P4.4 — Brand kit (retention feature)
5. P4.5 — Template library (acquisition feature)
6. P5.1 — Fabric.js canvas editor (big milestone)
