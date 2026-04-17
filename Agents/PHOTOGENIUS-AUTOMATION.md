# PhotoGenius AI — Hyperscale Solo Developer Automation Guide

> **Stack stays unchanged**: pnpm · Turborepo · Next.js 14 · FastAPI · Prisma → Supabase · Claude Haiku 4.5 · fal.ai · Google Vertex · WaveSpeed
> This guide adds **automation layers on top** — nothing replaces existing architecture.

---

## TABLE OF CONTENTS

1. [CLAUDE.md — Agent Memory File](#1-claudemd--agent-memory-file)
2. [MCP Servers — Connect Every Tool](#2-mcp-servers--connect-every-tool)
3. [Agent Teams — tmux Multi-Pane Setup](#3-agent-teams--tmux-multi-pane-setup)
4. [Error Automation Pipeline](#4-error-automation-pipeline)
5. [Feature Implementation Workflow](#5-feature-implementation-workflow)
6. [Prompt Caching — 70-90% Cost Reduction](#6-prompt-caching--70-90-cost-reduction)
7. [Semantic Quality Gate (LLM-as-Judge)](#7-semantic-quality-gate-llm-as-judge)
8. [Predictive Routing Upgrade](#8-predictive-routing-upgrade)
9. [CI/CD — GitHub Actions](#9-cicd--github-actions)
10. [Token Economics Reference](#10-token-economics-reference)

---

## 1. CLAUDE.md — Agent Memory File

Create this file at repo root. Claude Code reads it at the start of **every session**.

```markdown
# PhotoGenius AI — Claude Code Agent Memory

## Stack (DO NOT CHANGE)
- Package manager: pnpm (never npm/yarn)
- Monorepo: Turborepo
- Frontend: Next.js 14 · TypeScript · Tailwind · shadcn/ui
- Backend: FastAPI (Python) · port 8003
- Database: Prisma ORM → Supabase PostgreSQL (NO raw SQL from agents)
- Auth: DEV_USER pattern (Clerk removed, JWT pending Sprint 8)
- Deployment: PM2 on Ubuntu VPS · SSH: ubuntu@43.204.223.51

## 3-Provider Model Stack
- fal.ai: Flux 2 Flex, Ideogram v3, Recraft v4 Pro, Seedream 4.5
- Google Vertex: Imagen 4 Base/Fast/Ultra, Gemini 3 Imagen, Gemini 3.1 Imagen
- WaveSpeed: Grok 2 Imagine, Wan 2.7, Hunyuan Image

## 4-Agent Chain (Typography)
Master Strategist (Haiku 4.5) → Copy Writer (Gemini 2.5 Flash) → Image Prompter + Layout Planner (parallel, Gemini 2.5 Flash)

## Key File Locations
- Provider client: apps/api/app/services/external/multi_provider_client.py
- Model config: apps/api/app/services/smart/model_config.py
- Bucket detection: apps/api/app/services/smart/config.py
- SSE pipeline: apps/api/app/api/v1/endpoints/generate_stream.py
- Agent chain: apps/api/app/services/smart/design_agent_chain.py
- Quality critic: apps/api/app/services/smart/quality_critic.py
- Generate page: apps/web/app/(dashboard)/generate/page.tsx
- SSE proxy: apps/web/app/api/generate/stream/route.ts
- Admin: apps/web/app/admin/page.tsx

## Critical Rules for All Agents
1. Always use pnpm, NEVER npm or yarn
2. Never commit .env files — all secrets in .env.local or server env
3. Prisma for ALL DB operations — no raw SQL
4. Run migrations: pnpm prisma migrate dev
5. Python deps: pip install in apps/api virtualenv
6. Deploy: git pull → pnpm build → pm2 restart
7. Admin user: dev@photogenius.local (UUID: ee10a6d4-a124-4fea-ac1f-395d4f3adb6c)
8. Prompt caching: ALWAYS place static system prompts BEFORE dynamic user input
9. Feature flags live in admin panel → Feature Config tab (16 flags)

## Resolution Tiers
1K → 2K → 4K (NOT fast/balanced/quality/ultra — that's the old system)

## Active Feature Flags
USE_MASTER_STRATEGIST=true · USE_CLAUDE_ENGINE=true
USE_PROMPT_CACHING=true · USE_SMART_CACHE=true

## Current Sprint
Sprint 8 — Custom JWT Auth implementation
```

---

## 2. MCP Servers — Connect Every Tool

Create `.claude/mcp_config.json` at repo root:

```json
{
  "mcpServers": {
    "github": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-github"],
      "env": {
        "GITHUB_PERSONAL_ACCESS_TOKEN": "YOUR_GITHUB_PAT"
      }
    },
    "supabase": {
      "command": "npx",
      "args": ["-y", "@supabase/mcp-server-supabase@latest"],
      "env": {
        "SUPABASE_ACCESS_TOKEN": "YOUR_SUPABASE_TOKEN"
      }
    },
    "sentry": {
      "command": "npx",
      "args": ["-y", "@sentry/mcp-server"],
      "env": {
        "SENTRY_AUTH_TOKEN": "YOUR_SENTRY_TOKEN"
      }
    },
    "filesystem": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-filesystem", "/desktop/PhotoGenius AI"]
    }
  }
}
```

### Install MCPs
```bash
# GitHub MCP — read issues, create PRs, push fixes
npx -y @modelcontextprotocol/server-github

# Supabase MCP — inspect DB schema, run safe queries
npx -y @supabase/mcp-server-supabase@latest

# Sentry MCP — auto-feed production errors to agent context
npx -y @sentry/mcp-server
```

---

## 3. Agent Teams — tmux Multi-Pane Setup

### Install tmux (Ubuntu VPS)
```bash
sudo apt install tmux
```

### Start Agent Command Center
```bash
tmux new-session -s photogenius

# Split into 4 panes
Ctrl+B then %    # vertical split
Ctrl+B then "    # horizontal split
Ctrl+B then →↓   # navigate panes
```

### Pane Assignments

**Pane 1 — Team Lead (Opus)**
```bash
claude --model opus
# Role: Architecture decisions, sprint planning, code review
# Prompt: "You are the Tech Lead for PhotoGenius AI. Read CLAUDE.md first. 
# Coordinate the frontend and backend agents. Never change the core stack."
```

**Pane 2 — Backend Agent**
```bash
claude
# Role: FastAPI, Python agents, provider clients, quality critic
# Prompt: "You are the Python/FastAPI specialist for PhotoGenius AI.
# Work only in apps/api/. Read CLAUDE.md first. 
# Never change provider routing without checking model_config.py first."
```

**Pane 3 — Frontend Agent**
```bash
claude
# Role: Next.js, UI components, admin panel, SSE handling
# Prompt: "You are the Next.js specialist for PhotoGenius AI.
# Work only in apps/web/. Read CLAUDE.md first.
# Never use npm — always pnpm."
```

**Pane 4 — Error Monitor (24/7)**
```bash
claude
# Role: Watch Sentry, diagnose errors, propose patches
# Prompt: "You are the production error monitor for PhotoGenius AI.
# Check Sentry MCP for new errors every 10 minutes.
# For each error: locate the file, diagnose root cause, propose a fix.
# Write findings to ERRORS.md. Do not auto-apply — wait for approval."
```

### Shared Task Coordination
Create `TASKS.md` at root — all agents read/write this:

```markdown
# PhotoGenius AI — Agent Task Board

## IN PROGRESS
- [ ] Sprint 8: Custom JWT Auth

## ERRORS QUEUE
- (Error monitor writes here)

## FEATURE BACKLOG
- [ ] Sprint 3: Canvas Editor
- [ ] Sprint 4: Brand Kit
- [ ] Sprint 5: Batch Generation

## COMPLETED TODAY
- [x] (agents mark done here)
```

---

## 4. Error Automation Pipeline

### Step 1: Set Up Sentry

```bash
cd apps/web
pnpm add @sentry/nextjs
pnpm dlx @sentry/wizard@latest -i nextjs
```

For Python API:
```bash
cd apps/api
pip install sentry-sdk[fastapi]
```

Add to `apps/api/main.py`:
```python
import sentry_sdk
from sentry_sdk.integrations.fastapi import FastApiIntegration

sentry_sdk.init(
    dsn=os.getenv("SENTRY_DSN"),
    integrations=[FastApiIntegration()],
    traces_sample_rate=1.0,
    environment=os.getenv("ENVIRONMENT", "production"),
)
```

Add to `.env`:
```
SENTRY_DSN=https://xxx@oXXX.ingest.sentry.io/XXX
```

### Step 2: Error Auto-Diagnosis Workflow

When an error hits Sentry, the Error Monitor agent (Pane 4) follows this protocol:

```
1. Sentry MCP fires alert → agent receives error + stack trace
2. Agent locates exact file:line from stack trace
3. Agent reads surrounding 50 lines for context
4. Agent checks BUGS-AND-FIXES.md for similar past issues
5. Agent writes diagnosis + proposed fix to ERRORS.md
6. Agent pings you (Slack/notification) with summary
7. You approve → Backend or Frontend agent applies the fix
8. Agent writes fix to BUGS-AND-FIXES.md for future reference
```

### Step 3: Error Log Format (ERRORS.md)

```markdown
## [2026-04-17] ERROR: UUID validation failed in _generate_with_model

**Sentry**: https://sentry.io/issues/XXX
**File**: apps/api/app/services/smart/design_agent_chain.py:847
**Root Cause**: DEV_USER.id string passed instead of actual UUID from DB
**Fix**: Replace `DEV_USER.id` with `await get_user_uuid(email)` query
**Status**: PENDING APPROVAL
**Similar Past Bug**: See bugs-and-fixes.md → "UUID error" entry
```

---

## 5. Feature Implementation Workflow

### Standard Feature Flow

```
1. You describe feature in TASKS.md
2. Team Lead agent (Pane 1) breaks it into subtasks
3. Backend agent handles API changes
4. Frontend agent handles UI changes
5. Both agents write to TASKS.md when done
6. You test manually → approve
7. git commit → pm2 restart
```

### Feature Request Template

Write this in your chat to any agent:

```
FEATURE REQUEST:
Name: [Feature name]
Bucket: [Typography/Photorealism/Artistic/etc or General]
Files likely involved: [list files from CLAUDE.md Key Files section]
Constraints: 
  - Do not change pnpm/Turborepo/Prisma setup
  - Do not add new providers (3 providers only)
  - Feature flags go in admin panel Feature Config tab
  - Test with dev@photogenius.local user
Expected behavior: [describe what user sees]
```

### Adding New Feature Flags

All new features must be gated behind a flag in the admin panel:

```python
# apps/api/app/services/smart/config.py
# Add to feature flags section:
USE_NEW_FEATURE = os.getenv("USE_NEW_FEATURE", "false").lower() == "true"
```

Then expose in Admin → Feature Config tab (16 flags panel).

---

## 6. Prompt Caching — 70-90% Cost Reduction

> **From the PDF**: Prompt caching is the single most powerful lever for cost reduction.
> Claude Haiku 4.5: $1.00/M input → $0.10/M cached (90% savings).
> Gemini 2.5 Flash: $0.30/M input → $0.03/M cached (90% savings).

### The Golden Rule: Static Before Dynamic

```
WRONG ❌:
[Dynamic user input] → [Static system prompt]

CORRECT ✅:
[Static system prompt (cacheable)] → [Dynamic user input]
```

### Implementation in Design Agent Chain

Your `design_agent_chain.py` system prompts must follow this structure:

```python
# CORRECT — cache-friendly structure for Claude Haiku 4.5
messages = [
    {
        "role": "user",
        "content": [
            {
                # STATIC BLOCK — this gets cached after first call
                "type": "text",
                "text": MASTER_STRATEGIST_SYSTEM_PROMPT,  # 2000 tokens, never changes
                "cache_control": {"type": "ephemeral"}    # Anthropic cache marker
            },
            {
                # DYNAMIC BLOCK — appended after static prefix
                "type": "text", 
                "text": f"User brief: {user_brief}\nBrand: {brand_info}\nResolution: {resolution}"
            }
        ]
    }
]
```

### Anti-Patterns That Destroy Cache (NEVER DO THESE)

```python
# BREAKS CACHE ❌ — timestamp changes every call
system_prompt = f"{BASE_PROMPT}\nGenerated at: {datetime.now()}"

# BREAKS CACHE ❌ — session ID in static block
system_prompt = f"{BASE_PROMPT}\nSession: {session_id}"

# BREAKS CACHE ❌ — user data mixed into system prompt
system_prompt = f"You help {user.name} create images for {user.brand}..."
```

### Check Cache Hit Rate

Add to your quality critic or a monitoring endpoint:

```python
# After each Claude API call, log cache performance
usage = response.usage
cache_hit_rate = usage.cache_read_input_tokens / (usage.input_tokens + usage.cache_read_input_tokens)
logger.info(f"Cache hit rate: {cache_hit_rate:.1%} | Saved: {usage.cache_read_input_tokens} tokens")
```

---

## 7. Semantic Quality Gate (LLM-as-Judge)

> **From the PDF**: Syntactic heuristics (checking string length, keywords, uppercase) are fallacies. Replace with a semantic judge model that returns structured JSON scores.

### Current Quality Critic Upgrade

Your `quality_critic.py` already has 12 dimensions + Beast gates. Ensure the judge uses **binary/categorical scoring** (not 1-10 numerical), as LLMs struggle with granular numerical scales:

```python
# RUBRIC FOR SEMANTIC JUDGE — add to quality_critic.py

SEMANTIC_JUDGE_PROMPT = """
You are a quality evaluator for AI-generated creative assets. 
Evaluate the output against these dimensions. Return ONLY valid JSON.

Evaluation dimensions:
1. brand_consistency: Does it match brand tone and platform standards?
   Score: "pass" | "fail"
   
2. hook_efficacy: Does it capture attention without clickbait?
   Score: "low" | "medium" | "high"
   
3. constraint_adherence: Does it meet character limits and required inclusions?
   Score: "pass" | "fail"
   
4. persuasion_density: Ratio of compelling value props to generic filler?
   Score: "low" | "medium" | "high"

Return format:
{
  "brand_consistency": "pass",
  "hook_efficacy": "high",
  "constraint_adherence": "pass", 
  "persuasion_density": "medium",
  "rationale": "Brief explanation of scores",
  "overall": "pass" | "fail"
}

DO NOT return numerical scores. Binary and categorical only.
"""

# Cross-provider judging — use Claude Haiku to judge Gemini outputs
# This breaks self-enhancement bias (model preferring its own outputs)
async def semantic_judge(output: str, provider: str) -> dict:
    judge_model = "claude-haiku-4-5-20251001"  # Always Haiku for judging
    # temperature=0 for deterministic, repeatable scoring
    response = await anthropic_client.messages.create(
        model=judge_model,
        max_tokens=300,
        temperature=0,  # CRITICAL: deterministic scoring
        messages=[
            {"role": "user", "content": f"{SEMANTIC_JUDGE_PROMPT}\n\nOutput to evaluate:\n{output}"}
        ]
    )
    return json.loads(response.content[0].text)
```

### Bias Mitigation Rules (From PDF)

| Bias Type | Problem | Fix |
|-----------|---------|-----|
| Position Bias | Model favors first/last option | Randomize order in comparative prompts |
| Verbosity Bias | Longer = higher score | Penalize unnecessary length in rubric |
| Self-Enhancement | Model prefers same provider output | Always use cross-provider judge (Gemini gen → Claude judge) |

---

## 8. Predictive Routing Upgrade

> **From the PDF**: Reactive cascading (try cheap → fallback to expensive on failure) compounds latency. Predictive routing classifies BEFORE generation.

### Current State
Your `config.py` → `detect_capability_bucket()` already does this. Ensure it runs **before** any model call.

### Enhance with Complexity Classification

Add to `apps/api/app/services/smart/config.py`:

```python
# Complexity tiers for routing decisions
COMPLEXITY_TIERS = {
    "low": {
        # Simple promotional copy, standard photorealism
        # → Route directly to Gemini Flash / Seedream (cheap)
        "indicators": ["simple", "basic", "standard", "quick"],
        "max_agents": 2,
        "skip_master_strategist": True
    },
    "medium": {
        # Brand-aligned creative, multi-text typography
        # → Full 4-agent chain
        "indicators": ["brand", "typography", "multi-element"],
        "max_agents": 4,
        "skip_master_strategist": False  
    },
    "high": {
        # Regulatory, nuanced technical, ultra-quality
        # → Claude Haiku 4.5 direct, skip Gemini entirely
        "indicators": ["legal", "medical", "compliance", "ultra"],
        "max_agents": 4,
        "skip_master_strategist": False,
        "force_provider": "google_vertex"  # Imagen 4 Ultra
    }
}

def detect_complexity(prompt: str, bucket: str) -> str:
    """Classify before generation — eliminates reactive fallback latency."""
    prompt_lower = prompt.lower()
    
    if bucket == "fast":
        return "low"
    if bucket in ["typography", "photorealism"] and len(prompt) > 200:
        return "high"
    if any(word in prompt_lower for word in ["logo", "brand", "official", "legal"]):
        return "high"
    if any(word in prompt_lower for word in ["quick", "simple", "basic"]):
        return "low"
    return "medium"
```

---

## 9. CI/CD — GitHub Actions

Create `.github/workflows/ci.yml`:

```yaml
name: PhotoGenius AI CI/CD

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  test-and-build:
    runs-on: ubuntu-latest
    
    steps:
      - uses: actions/checkout@v4

      - uses: pnpm/action-setup@v3
        with:
          version: 9

      - uses: actions/setup-node@v4
        with:
          node-version: 20
          cache: 'pnpm'

      - name: Install dependencies
        run: pnpm install --frozen-lockfile

      - name: TypeScript check
        run: pnpm tsc --noEmit
        working-directory: apps/web

      - name: Build Next.js
        run: pnpm build
        working-directory: apps/web
        env:
          NEXT_PUBLIC_SUPABASE_URL: ${{ secrets.NEXT_PUBLIC_SUPABASE_URL }}
          NEXT_PUBLIC_SUPABASE_ANON_KEY: ${{ secrets.NEXT_PUBLIC_SUPABASE_ANON_KEY }}

      - name: Python lint (FastAPI)
        run: |
          pip install flake8
          flake8 apps/api/app --max-line-length=120 --ignore=E501,W503
        
      - name: Prisma migrate check
        run: pnpm prisma migrate status
        env:
          DATABASE_URL: ${{ secrets.DATABASE_URL }}
          DIRECT_URL: ${{ secrets.DIRECT_URL }}

  deploy:
    needs: test-and-build
    runs-on: ubuntu-latest
    if: github.ref == 'refs/heads/main' && github.event_name == 'push'
    
    steps:
      - name: Deploy to VPS
        uses: appleboy/ssh-action@v1.0.3
        with:
          host: 43.204.223.51
          username: ubuntu
          key: ${{ secrets.VPS_SSH_KEY }}
          script: |
            cd /home/ubuntu/photogenius
            git pull origin main
            pnpm install --frozen-lockfile
            pnpm build --filter=web
            pm2 restart photogenius-web
            pm2 restart photogenius-api
            pm2 save
```

### Required GitHub Secrets
Go to repo → Settings → Secrets → Actions:

```
DATABASE_URL          → Supabase connection string (pgbouncer)
DIRECT_URL            → Supabase direct connection
NEXT_PUBLIC_SUPABASE_URL
NEXT_PUBLIC_SUPABASE_ANON_KEY
VPS_SSH_KEY           → Contents of bimoraAI.pem
SENTRY_AUTH_TOKEN
GITHUB_PAT            → For MCP server
```

---

## 10. Token Economics Reference

> From PDF research — use these numbers for cost decisions.

| Model | Input/M | Cached Input/M | Output/M | Best For |
|-------|---------|----------------|---------|----------|
| Claude Haiku 4.5 | $1.00 | $0.10 | $5.00 | Master Strategist, Image Prompter, Judge |
| Gemini 2.5 Flash | $0.30 | $0.03 | $2.50 | Copy Writer (parallel Best-of-N) |
| Gemini 2.5 Flash-Lite | $0.10 | $0.01 | $0.40 | High-volume drafts |

### Cost Per Generation (With 90% Cache Hit Rate)

| Agent | Model | Cost |
|-------|-------|------|
| Master Strategist | Haiku 4.5 (cached) | ~$0.0082 |
| Copy Writer | Gemini 2.5 Flash (cached) | ~$0.0023 |
| Image Prompter | Haiku 4.5 (cached) | ~$0.0042 |
| Semantic Judge | Haiku 4.5 (cached) | ~$0.0012 |
| **Total per generation** | | **~$0.016** |

### Cost Optimization Priority
1. **Prompt caching** — biggest lever (70-90% savings). Already enabled via `USE_PROMPT_CACHING=true`
2. **Parallel Best-of-N** — use Gemini Flash-Lite for 3 parallel drafts, costs less than 1 Haiku call
3. **Predictive routing** — skip heavy agents for low-complexity requests
4. **Semantic judge at temperature=0** — deterministic, no wasted retry tokens

---

## QUICK REFERENCE COMMANDS

```bash
# Start all agents
tmux new-session -s photogenius

# SSH to server
ssh -i "C:\desktop\PhotoGenius AI\bimoraAI.pem" ubuntu@43.204.223.51

# Deploy
git pull && pnpm build --filter=web && pm2 restart all

# Check PM2 status
pm2 status && pm2 logs photogenius-api --lines 50

# Prisma studio (inspect DB)
pnpm prisma studio

# Run dev
pnpm dev  # starts both web (3002) and watches API

# Check cache hit rate (add to your monitoring)
grep "Cache hit rate" /var/log/photogenius/api.log | tail -20
```

---

## WORKFLOW: Daily Development Loop

```
Morning:
1. Check ERRORS.md — review what Error Monitor found overnight
2. Check TASKS.md — pick today's focus
3. Start tmux → 4 agent panes

During work:
4. Describe feature/fix to appropriate agent pane
5. Agent proposes changes → you review → approve
6. git commit with descriptive message
7. CI/CD auto-deploys to VPS

Evening:
8. Error Monitor runs overnight
9. Tomorrow morning → repeat
```

---

*This guide is tailored to PhotoGenius AI's exact stack. No library changes, no provider changes, no architecture changes — only automation layers on top.*
