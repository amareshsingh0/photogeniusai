# PhotoGenius AI — Active Error Queue

> Written by: Error Monitor Agent (Pane 4) from Sentry + PM2 logs
> Resolved by: Backend Agent (Pane 2) or Frontend Agent (Pane 3)
> After fix: move to RESOLVED section + add entry to BUGS-AND-FIXES.md

---

## HOW THIS WORKS

```
Error Monitor (24/7) watches:
  → Sentry (production errors + stack traces)
  → PM2 logs (api + web crashes)
  → API health endpoint responses

When error found:
  1. Error Monitor writes entry below under PENDING REVIEW
  2. You (human) read it → approve fix
  3. You type "fix [error ID]" to Backend or Frontend agent
  4. Agent applies fix → marks RESOLVED
  5. Agent copies lesson to BUGS-AND-FIXES.md
```

---

## PENDING REVIEW

> Errors waiting for your approval to fix.

*(empty — Error Monitor will populate this)*

---

## IN PROGRESS

> Errors currently being fixed by an agent.

*(empty)*

---

## RESOLVED

> Fixed errors — kept for 7 days, then moved to BUGS-AND-FIXES.md

*(empty — populated as errors get fixed)*

---

## ERROR ENTRY TEMPLATE

When Error Monitor writes a new error, it uses this format:

```markdown
### [ERR-001] Short description of error
**Date**: 2026-04-17 14:32 UTC
**Source**: Sentry | PM2-api | PM2-web | Health check
**Sentry URL**: https://sentry.io/issues/XXXXX (if available)
**Severity**: Low | Medium | High | Critical
**Affected**: All users | Admin only | Specific bucket | Specific model

**Stack Trace**:
​```
File "apps/api/app/services/smart/design_agent_chain.py", line 847, in _run_master_strategist
    user_uuid = await get_user_uuid(user.email)
AttributeError: 'NoneType' object has no attribute 'email'
​```

**File**: `apps/api/app/services/smart/design_agent_chain.py:847`
**Function**: `_run_master_strategist()`

**Diagnosis**:
Root cause: user object is None when DEV_USER fallback fails to load from DB.
The `get_user_uuid()` call happens before the None check.

**Proposed Fix**:
Move None check to line 844 before the UUID lookup:
​```python
if user is None:
    user = DEV_USER
if user.email is None:
    raise ValueError("User email required for generation")
user_uuid = await get_user_uuid(user.email)
​```

**Similar past bug**: See BUGS-AND-FIXES.md → "UUID error" entry (2026-04-08)
**Status**: PENDING APPROVAL
**Assigned to**: Backend Agent
```

---

## PM2 LOG COMMANDS (for Error Monitor)

```bash
# SSH first
ssh -i "C:\desktop\PhotoGenius AI\bimoraAI.pem" ubuntu@43.204.223.51

# Watch API errors in real time
pm2 logs photogenius-api --lines 200 --err

# Watch web errors
pm2 logs photogenius-web --lines 100 --err

# Full log (last 500 lines)
pm2 logs --lines 500

# Check if services are up
pm2 status

# Health check
curl -s https://api.creatives.bimoraai.com/health | python3 -m json.tool
```

---

## SENTRY SETUP (run this once — not done yet)

### FastAPI
```bash
cd apps/api
source venv/bin/activate
pip install sentry-sdk[fastapi]
```

Add to `apps/api/main.py` (top, before app creation):
```python
import sentry_sdk
from sentry_sdk.integrations.fastapi import FastApiIntegration

sentry_sdk.init(
    dsn=os.getenv("SENTRY_DSN"),
    integrations=[FastApiIntegration()],
    traces_sample_rate=0.2,
    environment=os.getenv("ENVIRONMENT", "production"),
    before_send=lambda event, hint: event  # add filters here if needed
)
```

### Next.js Web
```bash
cd apps/web
pnpm add @sentry/nextjs
pnpm dlx @sentry/wizard@latest -i nextjs
```

### Add to `.env` on server
```
SENTRY_DSN=https://xxx@oXXX.ingest.sentry.io/XXX
ENVIRONMENT=production
```

**Status**: NOT YET INSTALLED — add to TASKS.md Sprint backlog

---

## SEVERITY GUIDE

| Level | Meaning | Response Time |
|-------|---------|---------------|
| Critical | Generation completely broken, all users affected | Fix immediately |
| High | Feature broken for some users or some buckets | Fix same day |
| Medium | Degraded quality, wrong output, minor data issue | Fix this sprint |
| Low | UI glitch, log noise, non-breaking warning | Fix when convenient |

---

## KNOWN FLAKY AREAS (check here first)

These files have historically caused the most bugs — check them first when diagnosing:

1. `generate_stream.py` — SSE pipeline, parallel testing mode, DB writes
2. `multi_provider_client.py` — API timeouts, endpoint format changes
3. `design_agent_chain.py` — Agent token limits, parallel execution, context passing
4. `master_strategist.py` — Extended thinking budget, fallback paths
5. `apps/web/lib/auth.ts` — DEV_USER UUID, auth state
6. `apps/web/app/api/generate/stream/route.ts` — SSE proxy, DB save, error propagation
