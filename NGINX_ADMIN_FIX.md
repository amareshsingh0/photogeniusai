# NGINX Admin Panel Configuration Fix

## Problem
1. **creatives.bimoraai.com/admin** → Users see API domain (NEVER should happen)
2. **api.creatives.bimoraai.com/admin** → Double /admin/admin path or redirects to home

## Solution

### 1. On Production Server - Edit Nginx Config

```bash
# SSH to server
ssh -i "C:\desktop\PhotoGenius AI\bimoraAI.pem" ubuntu@43.204.223.51

# Backup current config
sudo cp /etc/nginx/sites-available/photogenius /etc/nginx/sites-available/photogenius.backup

# Edit Nginx config
sudo nano /etc/nginx/sites-available/photogenius
```

### 2. Nginx Configuration

Replace the entire file with this configuration:

```nginx
# WEB DOMAIN - Main user-facing website
server {
    listen 80;
    server_name creatives.bimoraai.com;

    # Redirect HTTP to HTTPS
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name creatives.bimoraai.com;

    # SSL certificates (managed by certbot)
    ssl_certificate /etc/letsencrypt/live/creatives.bimoraai.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/creatives.bimoraai.com/privkey.pem;

    # BLOCK ADMIN - Return 404 without exposing API domain
    location /admin {
        return 404;
    }

    # Block direct API access from web domain
    location /api/v1 {
        return 404;
    }

    # Next.js application (port 3002)
    location / {
        proxy_pass http://localhost:3002;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_cache_bypass $http_upgrade;
    }

    # Next.js static assets
    location /_next {
        proxy_pass http://localhost:3002;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_cache_bypass $http_upgrade;
    }
}

# API DOMAIN - Admin panel + API endpoints
server {
    listen 80;
    server_name api.creatives.bimoraai.com;

    # Redirect HTTP to HTTPS
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name api.creatives.bimoraai.com;

    # SSL certificates (managed by certbot)
    ssl_certificate /etc/letsencrypt/live/api.creatives.bimoraai.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/api.creatives.bimoraai.com/privkey.pem;

    # ADMIN PANEL - Serve from Next.js (no trailing slash to avoid double path)
    location /admin {
        proxy_pass http://localhost:3002;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_cache_bypass $http_upgrade;
    }

    # Auth endpoints - Next.js handles authentication
    location /api/auth {
        proxy_pass http://localhost:3002;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # Admin data endpoints - Next.js API routes
    location /api/admin {
        proxy_pass http://localhost:3002;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # Next.js static assets
    location /_next {
        proxy_pass http://localhost:3002;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
    }

    # FastAPI endpoints
    location /api/v1 {
        proxy_pass http://localhost:8003;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 600s;
        proxy_connect_timeout 600s;
        proxy_send_timeout 600s;
    }

    # Block access to non-API routes on API domain
    location / {
        return 404;
    }
}
```

### 3. Test and Apply Configuration

```bash
# Test Nginx configuration
sudo nginx -t

# If test passes, reload Nginx
sudo systemctl reload nginx

# Check Nginx status
sudo systemctl status nginx
```

### 4. Deploy Next.js Changes

```bash
# Navigate to project
cd /home/ubuntu/PhotoGenius-AI

# Pull latest code (admin layout fix)
git pull

# Rebuild Next.js
cd apps/web
pnpm install
pnpm build

# Restart PM2
pm2 restart photogenius-web

# Check status
pm2 status
pm2 logs photogenius-web --lines 30
```

### 5. Test After Deployment

**Test 1: Web domain admin block**
- URL: https://creatives.bimoraai.com/admin
- Expected: Clean 404 page (NOT redirected to API domain)
- User should NEVER see "api.creatives.bimoraai.com" anywhere

**Test 2: API domain admin access**
- URL: https://api.creatives.bimoraai.com/admin
- Expected: Admin login page or admin dashboard (if logged in)
- Should NOT show double /admin/admin in URL

**Test 3: Login to admin**
- URL: https://api.creatives.bimoraai.com/admin
- Login: dev@photogenius.local / password123
- Expected: Admin dashboard with Overview, Users, Generations, Settings tabs

## Key Principles

1. **Users should NEVER see API domain** - Web domain blocks all admin/API access cleanly
2. **Admin is API-domain only** - Only accessible at api.creatives.bimoraai.com/admin
3. **Clean separation** - No mixing of user features with admin controls
4. **No double paths** - Nginx proxy_pass without trailing slash prevents /admin/admin

## Common Issues

**Issue**: Still seeing double /admin/admin
**Fix**: Make sure `proxy_pass http://localhost:3002` has NO trailing `/admin` - let Next.js handle routing

**Issue**: Admin redirects to home
**Fix**: Make sure you're logged in with admin credentials (dev@photogenius.local / password123)

**Issue**: 502 Bad Gateway
**Fix**: Check `pm2 status` - photogenius-web must be running on port 3002
