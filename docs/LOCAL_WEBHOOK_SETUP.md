# Local Webhook Setup Guide

Complete guide for testing webhooks locally during development.

## Overview

PhotoGenius AI uses webhooks from:
- **Clerk** - User authentication events (user.created, user.updated, user.deleted)
- **Stripe** - Payment events (checkout.session.completed, subscription.updated)

## Prerequisites

1. **ngrok** or **Cloudflare Tunnel** installed
2. **Clerk** account with webhook configured
3. **Stripe** account (optional, for payment testing)

---

## Method 1: Using ngrok (Recommended)

### Step 1: Install ngrok

**Windows:**
```powershell
# Using Chocolatey
choco install ngrok

# Or download from https://ngrok.com/download
```

**macOS:**
```bash
brew install ngrok
```

**Linux:**
```bash
# Download from https://ngrok.com/download
# Or use snap
snap install ngrok
```

### Step 2: Get ngrok Auth Token

1. Sign up at https://ngrok.com (free)
2. Go to Dashboard → Your Authtoken
3. Copy your authtoken
4. Run: `ngrok config add-authtoken YOUR_TOKEN`

### Step 3: Start Your Local Server

```bash
# Terminal 1: Start Next.js dev server
cd apps/web
pnpm dev
# Server runs on http://localhost:3000
```

### Step 4: Expose Local Server with ngrok

```bash
# Terminal 2: Start ngrok tunnel
ngrok http 3000
```

You'll see output like:
```
Forwarding   https://abc123.ngrok-free.app -> http://localhost:3000
```

Copy the HTTPS URL (e.g., `https://abc123.ngrok-free.app`)

### Step 5: Configure Clerk Webhook

1. Go to Clerk Dashboard → Webhooks
2. Click "Add Endpoint"
3. Enter URL: `https://abc123.ngrok-free.app/api/webhooks/clerk`
4. Select events:
   - `user.created`
   - `user.updated`
   - `user.deleted`
5. Copy the **Signing Secret** → Add to `.env.local`:
   ```
   CLERK_WEBHOOK_SECRET=whsec_xxxxx
   ```
6. Click "Create"

### Step 6: Configure Stripe Webhook (Optional)

1. Install Stripe CLI: https://stripe.com/docs/stripe-cli
2. Login: `stripe login`
3. Forward webhooks to local server:
   ```bash
   stripe listen --forward-to localhost:3000/api/webhooks/stripe
   ```
4. Copy the webhook signing secret (starts with `whsec_`)
5. Add to `.env.local`:
   ```
   STRIPE_WEBHOOK_SECRET=whsec_xxxxx
   ```

### Step 7: Test Webhooks

**Test Clerk Webhook:**
1. Create a new user in your app
2. Check ngrok web interface: http://localhost:4040
3. Verify request was received and user created in database

**Test Stripe Webhook:**
1. Trigger test event:
   ```bash
   stripe trigger checkout.session.completed
   ```
2. Check your server logs for webhook processing

---

## Method 2: Using Cloudflare Tunnel (Alternative)

### Step 1: Install cloudflared

**Windows:**
```powershell
# Download from https://github.com/cloudflare/cloudflared/releases
# Or using Chocolatey
choco install cloudflared
```

**macOS:**
```bash
brew install cloudflared
```

### Step 2: Start Tunnel

```bash
# Start tunnel (no login required for quick testing)
cloudflared tunnel --url http://localhost:3000
```

You'll get a URL like: `https://random-subdomain.trycloudflare.com`

### Step 3: Configure Webhooks

Use the Cloudflare URL in Clerk/Stripe webhook settings (same as ngrok method above).

---

## Method 3: Using Stripe CLI (Stripe Only)

For Stripe webhooks, you can use Stripe CLI directly without ngrok:

```bash
# Install Stripe CLI
# Windows: Download from https://github.com/stripe/stripe-cli/releases
# macOS: brew install stripe/stripe-cli/stripe
# Linux: Download from releases page

# Login
stripe login

# Forward webhooks to local server
stripe listen --forward-to localhost:3000/api/webhooks/stripe

# In another terminal, trigger test events
stripe trigger checkout.session.completed
```

---

## Troubleshooting

### Webhook Not Receiving Events

1. **Check ngrok/Cloudflare tunnel is running**
   - Visit http://localhost:4040 (ngrok) to see requests
   - Check tunnel status in terminal

2. **Verify webhook URL is correct**
   - Must be HTTPS (not HTTP)
   - Must include full path: `/api/webhooks/clerk` or `/api/webhooks/stripe`

3. **Check webhook secret is set**
   ```bash
   # Verify in .env.local
   cat apps/web/.env.local | grep WEBHOOK_SECRET
   ```

4. **Check server logs**
   ```bash
   # Look for webhook processing errors
   # In Next.js dev server terminal
   ```

### Signature Verification Failed

- **Clerk**: Ensure `CLERK_WEBHOOK_SECRET` matches the signing secret from Clerk dashboard
- **Stripe**: Ensure `STRIPE_WEBHOOK_SECRET` matches the secret from `stripe listen` command

### Webhook Timeout

- Increase timeout in webhook handler if processing takes time
- Use background jobs for heavy processing

---

## Production Webhook Setup

For production, webhooks should point to your production domain:

**Clerk:**
```
https://yourdomain.com/api/webhooks/clerk
```

**Stripe:**
```
https://yourdomain.com/api/webhooks/stripe
```

**Important:**
- Use production webhook secrets (different from local)
- Enable webhook signing verification
- Monitor webhook delivery in service dashboards
- Set up retry logic for failed webhooks

---

## Quick Reference

### Environment Variables

```bash
# apps/web/.env.local
CLERK_WEBHOOK_SECRET=whsec_xxxxx          # From Clerk dashboard
STRIPE_WEBHOOK_SECRET=whsec_xxxxx          # From Stripe CLI or dashboard
```

### Useful Commands

```bash
# Start ngrok
ngrok http 3000

# View ngrok requests
open http://localhost:4040

# Stripe webhook forwarding
stripe listen --forward-to localhost:3000/api/webhooks/stripe

# Trigger test events
stripe trigger checkout.session.completed
stripe trigger customer.subscription.updated
```

---

## Security Notes

1. **Never commit webhook secrets** to git
2. **Use different secrets** for dev/staging/production
3. **Verify webhook signatures** (already implemented in code)
4. **Rate limit webhook endpoints** in production
5. **Monitor webhook delivery** for failures

---

## Additional Resources

- [ngrok Documentation](https://ngrok.com/docs)
- [Stripe CLI Documentation](https://stripe.com/docs/stripe-cli)
- [Clerk Webhooks Guide](https://clerk.com/docs/integrations/webhooks/overview)
- [Cloudflare Tunnel Docs](https://developers.cloudflare.com/cloudflare-one/connections/connect-apps/)
