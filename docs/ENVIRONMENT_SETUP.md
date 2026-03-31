# Environment Setup Guide

Complete guide for setting up PhotoGenius AI environment variables and required services.

## Quick Start

```bash
# Copy example files
# Ensure apps/web/.env.local and apps/api/.env.local exist (create and fill per this doc)
# aws/sagemaker: use aws/sagemaker/.env.local when running deploy from that directory

# Fill in your API keys (see sections below)
nano apps/web/.env.local
nano apps/api/.env.local

# Verify setup
pnpm run verify-env
```

## Required API Keys & Services

### 1. Clerk (Authentication) ⚠️ Required

**Website**: https://clerk.com

**Steps**:

1. Create account & new application
2. Copy "Publishable Key" → `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY`
3. Copy "Secret Key" → `CLERK_SECRET_KEY`
4. Enable Email/Password authentication
5. Configure OAuth providers (Google, GitHub) if needed
6. Set up webhooks (optional but recommended):
   - URL: `https://your-domain.com/api/webhooks/clerk`
   - Events: `user.created`, `user.updated`, `user.deleted`

**Free Tier**: 10,000 MAU (Monthly Active Users)

---

### 2. Supabase (Database) ⚠️ Required

**Website**: https://supabase.com

**Steps**:

1. Create new project
2. Wait for provisioning (~2 minutes)
3. Go to Settings → Database
4. Copy "Connection string" (Session mode)
5. Replace `[YOUR-PASSWORD]` with your database password
6. Add to `DATABASE_URL` in `apps/api/.env.local`

**Format**: `postgresql+asyncpg://postgres:[PASSWORD]@db.[PROJECT].supabase.co:5432/postgres`

**Free Tier**: 500MB database, 2GB bandwidth

---

### 3. Upstash Redis ⚠️ Required

**Website**: https://upstash.com

**Steps**:

1. Create Redis database
2. Choose region close to your users
3. Copy connection string
4. Add to `REDIS_URL` in `apps/api/.env.local`

**Format**: `redis://default:[PASSWORD]@[ENDPOINT]:[PORT]`

**Free Tier**: 10,000 commands/day

**Alternative**: Run local Redis with Docker:

```bash
docker run -d -p 6379:6379 redis:alpine
```

---

### 4. AWS S3 or Cloudflare R2 ⚠️ Required

#### Option A: AWS S3

**Website**: https://console.aws.amazon.com

**Steps**:

1. Create S3 bucket (e.g., `photogenius-prod`)
2. Block all public access: OFF (or configure bucket policy)
3. Enable versioning (optional)
4. Create IAM user with S3 access:
   - Policy: `AmazonS3FullAccess` (or custom with `s3:PutObject`, `s3:GetObject`, `s3:DeleteObject`)
5. Generate access keys
6. Add to `apps/api/.env.local`:
   - `AWS_ACCESS_KEY_ID`
   - `AWS_SECRET_ACCESS_KEY`
   - `AWS_REGION`
   - `S3_BUCKET_NAME`

#### Option B: Cloudflare R2 (Recommended - Free egress)

**Website**: https://dash.cloudflare.com

**Steps**:

1. Go to R2 → Create bucket
2. Create API token with R2 permissions
3. Add to `apps/api/.env.local`:
   - `AWS_ACCESS_KEY_ID` (from R2 API token)
   - `AWS_SECRET_ACCESS_KEY` (from R2 API token)
   - `AWS_REGION=auto`
   - `S3_BUCKET_NAME=your-bucket-name`
   - `S3_ENDPOINT=https://[ACCOUNT_ID].r2.cloudflarestorage.com`

**Free Tier**: 10GB storage, unlimited egress

---

### 5. HuggingFace ⚠️ Required

**Website**: https://huggingface.co

**Steps**:

1. Create account
2. Go to Settings → Access Tokens
3. Create new token with "Read" access
4. Add to `HUGGINGFACE_TOKEN` in `apps/api/.env.local`

**Free Tier**: Unlimited model downloads

---

### 6. Modal.com (GPU Compute) ⚠️ Required for AI Generation

**Website**: https://modal.com

**Steps**:

1. Create account
2. Install CLI: `pip install modal`
3. Run `modal token new`
4. Copy token ID and secret
5. Add to `apps/api/.env.local`:
   - `MODAL_TOKEN_ID`
   - `MODAL_TOKEN_SECRET`

**Free Tier**: $30/month credit

---

### 7. Stripe (Payments) ⚠️ Optional

**Website**: https://stripe.com

**Steps**:

1. Create account
2. Go to Developers → API keys
3. Copy "Publishable key" → `NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY`
4. Copy "Secret key" → `STRIPE_SECRET_KEY`
5. For webhooks:
   - Developers → Webhooks → Add endpoint
   - URL: `https://your-domain.com/api/webhooks/stripe`
   - Events: `checkout.session.completed`, `customer.subscription.updated`
   - Copy webhook secret → `STRIPE_WEBHOOK_SECRET`

**Free Tier**: No monthly fee, 2.9% + $0.30 per transaction

---

### 8. Sentry (Error Tracking) ⚠️ Optional

**Website**: https://sentry.io

**Steps**:

1. Create project (Next.js for frontend, Python for backend)
2. Copy DSN
3. Add to `apps/web/.env.local`:
   - `NEXT_PUBLIC_SENTRY_DSN`
4. Add to `apps/api/.env.local`:
   - `SENTRY_DSN`

**Free Tier**: 5,000 events/month

---

### 9. PostHog (Analytics) ⚠️ Optional

**Website**: https://posthog.com

**Steps**:

1. Create account
2. Create project
3. Copy project API key
4. Add to `apps/web/.env.local`:
   - `NEXT_PUBLIC_POSTHOG_KEY`
   - `NEXT_PUBLIC_POSTHOG_HOST` (usually `https://app.posthog.com`)

**Free Tier**: 1M events/month

---

## Environment Setup Commands

### Development

```bash
# 1. Copy example files
# Ensure apps/web/.env.local and apps/api/.env.local exist (create and fill per this doc)
# aws/sagemaker: use aws/sagemaker/.env.local when running deploy from that directory

# 2. Fill in your API keys
nano apps/web/.env.local
nano apps/api/.env.local

# 3. Verify configuration
pnpm run verify-env

# 4. Setup database
cd packages/database
pnpm prisma generate
pnpm prisma migrate dev
pnpm prisma db seed

# 5. Start development servers
pnpm dev
```

### Production

See [DEPLOYMENT.md](./DEPLOYMENT.md) for production deployment guide.

---

## Troubleshooting

### Database Connection Failed

**Symptoms**: `Connection refused` or `timeout` errors

**Solutions**:

- Check if PostgreSQL is running: `docker ps` or `psql -h localhost -U postgres`
- Verify `DATABASE_URL` format: `postgresql+asyncpg://user:password@host:port/db`
- Ensure firewall allows connection
- For Supabase: Check if IP is whitelisted in dashboard

### S3 Upload Failed

**Symptoms**: `403 Forbidden` or `Access Denied` errors

**Solutions**:

- Verify IAM user has `s3:PutObject` permission
- Check bucket CORS configuration:
  ```json
  [
    {
      "AllowedOrigins": ["*"],
      "AllowedMethods": ["GET", "PUT", "POST", "DELETE"],
      "AllowedHeaders": ["*"],
      "ExposeHeaders": ["ETag"]
    }
  ]
  ```
- Ensure bucket name is correct
- For R2: Verify `S3_ENDPOINT` is correct

### Model Download Timeout

**Symptoms**: `Connection timeout` when downloading models

**Solutions**:

- Check `HUGGINGFACE_TOKEN` is valid
- Try downloading manually first: `huggingface-cli download model-name`
- Increase timeout settings in code
- Use VPN if in restricted region

### Clerk Authentication Not Working

**Symptoms**: `401 Unauthorized` or redirect loops

**Solutions**:

- Verify `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY` and `CLERK_SECRET_KEY` match
- Check Clerk dashboard → API Keys
- Ensure webhook URL is correct (if using webhooks)
- Clear browser cookies and try again

### Redis Connection Failed

**Symptoms**: `Connection refused` errors

**Solutions**:

- Check if Redis is running: `redis-cli ping`
- Verify `REDIS_URL` format: `redis://host:port/db`
- For Upstash: Check if database is active in dashboard
- Test connection: `redis-cli -u $REDIS_URL ping`

---

## Security Checklist

Before deploying to production:

- [ ] All `.env` files in `.gitignore`
- [ ] Different keys for dev/staging/prod
- [ ] Rotate keys every 90 days
- [ ] Use secrets manager in production (AWS Secrets Manager, Vercel Env, etc.)
- [ ] Enable MFA on all service accounts
- [ ] Restrict API key permissions to minimum required
- [ ] Enable rate limiting on all public endpoints
- [ ] Use HTTPS for all API calls
- [ ] Enable CORS only for trusted origins
- [ ] Review and audit all third-party service access logs

---

## Environment Variable Reference

### Frontend (`apps/web/.env.local`)

| Variable                             | Required | Description                                  |
| ------------------------------------ | -------- | -------------------------------------------- |
| `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY`  | ✅       | Clerk publishable key                        |
| `CLERK_SECRET_KEY`                   | ✅       | Clerk secret key                             |
| `NEXT_PUBLIC_API_URL`                | ✅       | Backend API URL                              |
| `NEXT_PUBLIC_WS_URL`                 | ✅       | WebSocket URL                                |
| `NEXT_PUBLIC_APP_URL`                | ✅       | Frontend app URL                             |
| `NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY` | ⚠️       | Stripe publishable key (if payments enabled) |
| `NEXT_PUBLIC_SENTRY_DSN`             | ⚠️       | Sentry DSN (optional)                        |
| `NEXT_PUBLIC_POSTHOG_KEY`            | ⚠️       | PostHog API key (optional)                   |

### Backend (`apps/api/.env.local`)

| Variable                | Required | Description                             |
| ----------------------- | -------- | --------------------------------------- |
| `DATABASE_URL`          | ✅       | PostgreSQL connection string            |
| `REDIS_URL`             | ✅       | Redis connection string                 |
| `CLERK_SECRET_KEY`      | ✅       | Clerk secret key                        |
| `AWS_ACCESS_KEY_ID`     | ✅       | AWS/R2 access key                       |
| `AWS_SECRET_ACCESS_KEY` | ✅       | AWS/R2 secret key                       |
| `S3_BUCKET_NAME`        | ✅       | S3/R2 bucket name                       |
| `HUGGINGFACE_TOKEN`     | ✅       | HuggingFace API token                   |
| `MODAL_TOKEN_ID`        | ✅       | Modal token ID                          |
| `MODAL_TOKEN_SECRET`    | ✅       | Modal token secret                      |
| `STRIPE_SECRET_KEY`     | ⚠️       | Stripe secret key (if payments enabled) |

---

## Support

If you encounter issues:

1. Check [Troubleshooting](#troubleshooting) section
2. Run `pnpm run verify-env` to validate configuration
3. Check service dashboards for status
4. Review application logs for detailed error messages

For additional help, see the main [README.md](../README.md).
