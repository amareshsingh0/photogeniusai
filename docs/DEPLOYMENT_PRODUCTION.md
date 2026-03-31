# Production Deployment Guide

Complete guide for deploying PhotoGenius AI to production environments.

## Prerequisites

- Production domain with SSL certificate
- Database (PostgreSQL) - Supabase, AWS RDS, or self-hosted
- Object Storage (S3/R2) configured
- Redis instance (Upstash, AWS ElastiCache, or self-hosted)
- All API keys and secrets ready

---

## Deployment Options

### Option 1: Vercel (Frontend) + Railway (Backend)

**Best for:** Quick deployment, managed infrastructure

#### Frontend (Vercel)

1. **Connect Repository**
   - Go to https://vercel.com
   - Import your GitHub repository
   - Select `apps/web` as root directory

2. **Configure Environment Variables**
   ```
   NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=...
   CLERK_SECRET_KEY=...
   NEXT_PUBLIC_API_URL=https://your-api.railway.app
   DATABASE_URL=...
   # ... all other env vars
   ```

3. **Deploy**
   - Push to `main` branch triggers auto-deploy
   - Or manually deploy from Vercel dashboard

#### Backend (Railway)

1. **Create Project**
   - Go to https://railway.app
   - New Project → Deploy from GitHub
   - Select `apps/api` directory

2. **Configure Environment**
   - Add all environment variables
   - Set Python version: `3.11`
   - Add build command: `pip install -r requirements.txt`
   - Add start command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`

3. **Database Migration**
   ```bash
   railway run alembic upgrade head
   ```

4. **Deploy**
   - Railway auto-deploys on push to main

---

### Option 2: Docker Compose (Self-Hosted)

**Best for:** Full control, cost-effective

#### Step 1: Create docker-compose.yml

```yaml
# docker-compose.prod.yml
version: '3.8'

services:
  postgres:
    image: postgres:15-alpine
    environment:
      POSTGRES_DB: photogenius
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: ${DB_PASSWORD}
    volumes:
      - postgres_data:/var/lib/postgresql/data
    ports:
      - "5432:5432"

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data

  api:
    build:
      context: ./apps/api
      dockerfile: Dockerfile
    environment:
      DATABASE_URL: postgresql+asyncpg://postgres:${DB_PASSWORD}@postgres:5432/photogenius
      REDIS_URL: redis://redis:6379/0
      # ... other env vars
    ports:
      - "8000:8000"
    depends_on:
      - postgres
      - redis

  web:
    build:
      context: ./apps/web
      dockerfile: Dockerfile
    environment:
      NEXT_PUBLIC_API_URL: http://api:8000
      # ... other env vars
    ports:
      - "3000:3000"
    depends_on:
      - api

volumes:
  postgres_data:
  redis_data:
```

#### Step 2: Build and Deploy

```bash
# Build images
docker-compose -f docker-compose.prod.yml build

# Run migrations
docker-compose -f docker-compose.prod.yml run api alembic upgrade head

# Start services
docker-compose -f docker-compose.prod.yml up -d

# View logs
docker-compose -f docker-compose.prod.yml logs -f
```

---

### Option 3: Kubernetes (K8s)

**Best for:** Scalability, enterprise

#### Step 1: Create Kubernetes Manifests

```yaml
# k8s/api-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: photogenius-api
spec:
  replicas: 3
  selector:
    matchLabels:
      app: photogenius-api
  template:
    metadata:
      labels:
        app: photogenius-api
    spec:
      containers:
      - name: api
        image: your-registry/photogenius-api:latest
        env:
        - name: DATABASE_URL
          valueFrom:
            secretKeyRef:
              name: photogenius-secrets
              key: database-url
        ports:
        - containerPort: 8000
---
apiVersion: v1
kind: Service
metadata:
  name: photogenius-api
spec:
  selector:
    app: photogenius-api
  ports:
  - port: 80
    targetPort: 8000
  type: LoadBalancer
```

#### Step 2: Deploy to K8s

```bash
# Apply manifests
kubectl apply -f k8s/

# Check status
kubectl get pods
kubectl get services

# View logs
kubectl logs -f deployment/photogenius-api
```

---

## Pre-Deployment Checklist

### Security

- [ ] All secrets in environment variables (not in code)
- [ ] HTTPS enabled (SSL certificates configured)
- [ ] CORS configured for production domain only
- [ ] Rate limiting enabled
- [ ] Webhook signatures verified
- [ ] Database credentials rotated
- [ ] API keys have minimum required permissions
- [ ] Security headers configured (CSP, HSTS, etc.)

### Database

- [ ] Production database created and accessible
- [ ] Migrations tested in staging
- [ ] Backup strategy configured
- [ ] Connection pooling configured
- [ ] Read replicas (if needed for scale)

### Storage

- [ ] S3/R2 bucket created
- [ ] CORS configured
- [ ] CDN configured (Cloudflare, CloudFront)
- [ ] Image optimization enabled

### Monitoring

- [ ] Error tracking (Sentry) configured
- [ ] Analytics (PostHog) configured
- [ ] Logging aggregation (Datadog, LogRocket)
- [ ] Uptime monitoring (Pingdom, UptimeRobot)
- [ ] Performance monitoring (New Relic, AppDynamics)

### Performance

- [ ] CDN configured for static assets
- [ ] Image optimization enabled
- [ ] Database indexes created
- [ ] Redis caching configured
- [ ] API response caching where appropriate

---

## Environment Variables

### Frontend (Production)

```bash
NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=pk_live_...
CLERK_SECRET_KEY=sk_live_...
NEXT_PUBLIC_API_URL=https://api.yourdomain.com
NEXT_PUBLIC_APP_URL=https://yourdomain.com
NEXT_PUBLIC_WS_URL=wss://api.yourdomain.com
NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY=pk_live_...
```

### Backend (Production)

```bash
DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/db
REDIS_URL=redis://host:6379/0
CLERK_SECRET_KEY=sk_live_...
AWS_ACCESS_KEY_ID=...
AWS_SECRET_ACCESS_KEY=...
S3_BUCKET_NAME=photogenius-prod
HUGGINGFACE_TOKEN=...
MODAL_TOKEN_ID=...
MODAL_TOKEN_SECRET=...
STRIPE_SECRET_KEY=sk_live_...
STRIPE_WEBHOOK_SECRET=whsec_...
SENTRY_DSN=...
ENVIRONMENT=production
```

---

## Database Migration in Production

```bash
# Connect to production
export DATABASE_URL="postgresql+asyncpg://..."

# Run migrations
cd apps/api
alembic upgrade head

# Verify
alembic current

# Rollback if needed (careful!)
alembic downgrade -1
```

**Important:**
- Always backup database before migrations
- Test migrations in staging first
- Run migrations during low-traffic periods
- Have rollback plan ready

---

## Webhook Configuration

### Clerk Webhooks

1. Go to Clerk Dashboard → Webhooks
2. Add endpoint: `https://yourdomain.com/api/webhooks/clerk`
3. Select events: `user.created`, `user.updated`, `user.deleted`
4. Copy signing secret → `CLERK_WEBHOOK_SECRET`

### Stripe Webhooks

1. Go to Stripe Dashboard → Webhooks
2. Add endpoint: `https://yourdomain.com/api/webhooks/stripe`
3. Select events:
   - `checkout.session.completed`
   - `customer.subscription.updated`
   - `customer.subscription.deleted`
4. Copy signing secret → `STRIPE_WEBHOOK_SECRET`

---

## Monitoring & Alerts

### Health Checks

```python
# apps/api/app/api/v1/endpoints/health.py
@router.get("/health")
async def health_check():
    # Check database
    # Check Redis
    # Check S3
    return {"status": "healthy"}
```

### Uptime Monitoring

- Set up Pingdom/UptimeRobot to check `/health` endpoint
- Alert on downtime > 1 minute
- Alert on response time > 2 seconds

### Error Alerts

- Sentry alerts for critical errors
- Email/Slack notifications for 5xx errors
- Alert on error rate > 1%

---

## Scaling Considerations

### Horizontal Scaling

- Run multiple API instances behind load balancer
- Use Redis for session storage (not in-memory)
- Use database connection pooling
- Use CDN for static assets

### Vertical Scaling

- Increase database instance size
- Add more CPU/RAM to API servers
- Use GPU instances for AI generation (Modal.com)

### Caching Strategy

- Cache frequently accessed data in Redis
- Cache API responses where appropriate
- Use CDN for images and static files
- Implement database query caching

---

## Backup & Disaster Recovery

### Database Backups

```bash
# Automated daily backups
pg_dump $DATABASE_URL > backup_$(date +%Y%m%d).sql

# Restore
psql $DATABASE_URL < backup_20240126.sql
```

### File Storage Backups

- Enable S3 versioning
- Configure lifecycle policies
- Regular backup to separate region

### Disaster Recovery Plan

1. Document recovery procedures
2. Test restore process quarterly
3. Keep backups in multiple regions
4. Document rollback procedures

---

## Cost Optimization

### Infrastructure

- Use reserved instances for predictable workloads
- Auto-scale down during low traffic
- Use spot instances for non-critical workloads
- Monitor and optimize database queries

### Third-Party Services

- Monitor API usage (HuggingFace, Modal)
- Set up billing alerts
- Optimize image storage (compression, formats)
- Use CDN to reduce bandwidth costs

---

## Security Hardening

### Network

- Use VPC for database (not publicly accessible)
- Enable firewall rules
- Use private networking between services
- Enable DDoS protection (Cloudflare)

### Application

- Enable rate limiting
- Implement request size limits
- Sanitize all user inputs
- Use parameterized queries (prevent SQL injection)
- Enable CSRF protection

### Secrets Management

- Use secrets manager (AWS Secrets Manager, Vault)
- Rotate secrets every 90 days
- Never commit secrets to git
- Use different secrets for each environment

---

## Post-Deployment

### Verification

1. Test all critical user flows
2. Verify webhooks are receiving events
3. Check error logs for issues
4. Monitor performance metrics
5. Verify SSL certificates
6. Test backup/restore process

### Documentation

- Update API documentation
- Document deployment process
- Create runbooks for common issues
- Document rollback procedures

---

## Support & Maintenance

### Regular Tasks

- Weekly: Review error logs
- Monthly: Review performance metrics
- Quarterly: Security audit
- Quarterly: Test disaster recovery

### Updates

- Keep dependencies updated
- Apply security patches promptly
- Test updates in staging first
- Have rollback plan for updates

---

## Additional Resources

- [Vercel Deployment Guide](https://vercel.com/docs)
- [Railway Documentation](https://docs.railway.app)
- [Docker Best Practices](https://docs.docker.com/develop/dev-best-practices/)
- [Kubernetes Documentation](https://kubernetes.io/docs/)
- [Production Checklist](https://github.com/mtdowling/production-checklist)
