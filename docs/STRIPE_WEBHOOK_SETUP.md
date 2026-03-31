# Stripe Webhook Setup & Testing

## Overview

The Stripe webhook at `POST /api/webhooks/stripe` handles:

| Event | Action |
|-------|--------|
| `checkout.session.completed` | Credit top-up (one-time or first subscription payment); update user tier and subscription |
| `invoice.payment_succeeded` | Subscription renewal: add credits, extend `subscriptionEndsAt`, log transaction |
| `invoice.payment_failed` | Downgrade user to FREE, clear subscription, log failed transaction |
| `customer.subscription.deleted` | Clear subscription and downgrade user to FREE |

Security: webhook signature verification, idempotency (by Stripe event ID), rate limit (120 req/min per IP), and atomic DB transactions for credit updates.

---

## Environment Variables

```env
STRIPE_SECRET_KEY=sk_...
STRIPE_WEBHOOK_SECRET=whsec_...   # From Stripe Dashboard or CLI

# Optional: price → credits/tier (for subscription and credit packs)
STRIPE_PRICE_PRO=price_xxxxx
STRIPE_CREDITS_PRO=100
STRIPE_NAME_PRO=Pro Monthly

STRIPE_PRICE_PREMIUM=price_yyyyy
STRIPE_CREDITS_PREMIUM=500
STRIPE_NAME_PREMIUM=Premium Monthly

STRIPE_DEFAULT_CREDIT_PACK=50   # Credits when price not in map (one-time or dev)
```

---

## Database

### New table: `stripe_webhook_events` (idempotency)

If you use `prisma db push`, the table is created from the schema. Otherwise run:

```sql
-- If not using Prisma migrate/push, run this (column names match Prisma schema):
CREATE TABLE "stripe_webhook_events" (
  "id" UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  "eventId" VARCHAR(255) NOT NULL UNIQUE,
  "eventType" VARCHAR(100) NOT NULL,
  "processedAt" TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE UNIQUE INDEX "stripe_webhook_events_eventId_key" ON "stripe_webhook_events"("eventId");
CREATE INDEX "stripe_webhook_events_eventType_idx" ON "stripe_webhook_events"("eventType");
```

---

## Reconciliation SQL Queries

Run against your Postgres DB (e.g. `transactions` and `users` tables).

### 1. Credits vs transactions (sum of completed credits)

```sql
-- Total credits added by transactions (column names match Prisma schema)
SELECT
  SUM("creditsAdded") AS total_credits_added,
  COUNT(*) FILTER (WHERE status = 'COMPLETED') AS completed_count,
  COUNT(*) FILTER (WHERE status = 'FAILED') AS failed_count
FROM transactions
WHERE "creditsAdded" IS NOT NULL AND "creditsAdded" > 0;
```

### 2. Per-user balance reconciliation

```sql
-- User balances vs sum of transaction deltas (Prisma column names)
SELECT
  u.id,
  u.email,
  u."creditsBalance" AS current_balance,
  u.tier,
  COALESCE(SUM(t."creditsAdded"), 0) AS total_credits_from_transactions
FROM users u
LEFT JOIN transactions t ON t."userId" = u.id AND t.status = 'COMPLETED' AND t."creditsAdded" > 0
GROUP BY u.id, u.email, u."creditsBalance", u.tier;
```

### 3. Stripe event processing audit

```sql
-- Webhook events processed in last 24h
SELECT "eventType", COUNT(*), MIN("processedAt"), MAX("processedAt")
FROM stripe_webhook_events
WHERE "processedAt" > NOW() - INTERVAL '24 hours'
GROUP BY "eventType"
ORDER BY "eventType";
```

### 4. Failed payments and downgrades

```sql
-- Failed Stripe transactions (invoice.payment_failed)
SELECT id, "userId", amount, "stripeInvoiceId", "failureReason", "createdAt"
FROM transactions
WHERE status = 'FAILED' AND "stripeInvoiceId" IS NOT NULL
ORDER BY "createdAt" DESC
LIMIT 100;
```

### 5. Subscription revenue (completed)

```sql
-- Revenue by type (subscription vs credit pack)
SELECT type, status, COUNT(*), SUM(amount) AS total_cents
FROM transactions
WHERE status = 'COMPLETED'
GROUP BY type, status
ORDER BY type, status;
```

---

## Testing with Stripe CLI

### 1. Install Stripe CLI

- Windows: `scoop install stripe` or download from https://stripe.com/docs/stripe-cli
- Mac: `brew install stripe/stripe-cli/stripe`

### 2. Login and forward webhooks to local

```bash
stripe login
stripe listen --forward-to localhost:3000/api/webhooks/stripe
```

The CLI prints a **webhook signing secret** like `whsec_...`. Set it in `.env.local`:

```env
STRIPE_WEBHOOK_SECRET=whsec_xxxxx
```

Restart the Next.js dev server so it picks up the new secret.

### 3. Trigger test events

In a second terminal:

```bash
# One-time checkout completed (use a test customer id if you have one)
stripe trigger checkout.session.completed

# Invoice paid (subscription renewal)
stripe trigger invoice.payment_succeeded

# Invoice payment failed
stripe trigger invoice.payment_failed

# Subscription cancelled
stripe trigger customer.subscription.deleted
```

**Note:** Triggered events use Stripe’s test data. Your app will only update DB if it finds a user by `stripeCustomerId` (or `stripeSubscriptionId` for subscription.deleted). For full flow tests:

1. Create a test user in your DB with `stripe_customer_id = 'cus_...'` from Stripe test mode.
2. Or create a Checkout Session in test mode, complete it, then use the same customer/subscription ids in your DB.

### 4. Verify idempotency

Send the same event body and signature twice (e.g. replay from Stripe Dashboard or resend from CLI). The second request should return `200` with `{ "received": true, "duplicate": true }` and must not double-apply credits.

### 5. Verify signature rejection

Call the webhook without the `stripe-signature` header or with an invalid body; expect `400 Invalid signature`.

---

## Checklist

- [ ] `STRIPE_WEBHOOK_SECRET` and `STRIPE_SECRET_KEY` set in env
- [ ] Table `stripe_webhook_events` exists (via Prisma push or migration)
- [ ] Price/credits env vars set if using subscription or credit packs
- [ ] Users have `stripeCustomerId` set when they start checkout (so webhook can find them)
- [ ] Stripe Dashboard → Webhooks → endpoint URL points to `https://your-domain/api/webhooks/stripe`
- [ ] Test with Stripe CLI and confirm transactions and user credits/tier in DB
