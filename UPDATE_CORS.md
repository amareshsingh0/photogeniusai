# CORS Update Required for Admin Panel

## Problem
The admin panel at `https://creatives.bimoraai.com/admin` cannot fetch data from `https://api.creatives.bimoraai.com` due to CORS restrictions.

## Solution
Update ALLOWED_ORIGINS in the API .env file to include the frontend domain.

## Steps on Production Server

1. SSH to server:
```bash
ssh -i ~/.ssh/your-key.pem ubuntu@43.204.223.51
```

2. Edit API .env file:
```bash
nano /home/ubuntu/PhotoGenius-AI/apps/api/.env.local
```

3. Find the line with `ALLOWED_ORIGINS` and update it to:
```env
ALLOWED_ORIGINS=["http://localhost:3000","http://localhost:3002","https://creatives.bimoraai.com"]
```

4. Save and exit (Ctrl+X, then Y, then Enter)

5. Restart the API service:
```bash
pm2 restart photogenius-api
```

6. Check logs to ensure it restarted successfully:
```bash
pm2 logs photogenius-api --lines 50
```

## What Changed

### 1. FastAPI Admin Endpoint (apps/api/app/api/v1/endpoints/admin.py)
- Added comprehensive `/api/v1/admin/analytics` endpoint
- Matches the structure expected by the admin UI
- Returns:
  - Overview stats (total users, generations, active users, credits)
  - Generation breakdown (today/week/month)
  - Breakdown by tier and bucket
  - Recent 10 generations with user info
  - User growth over 30 days

### 2. Admin Page Frontend (apps/web/app/(dashboard)/admin/page.tsx)
- Updated `fetchAnalytics()` to call FastAPI backend instead of Next.js route
- URL changed from `/api/admin/analytics` to `${NEXT_PUBLIC_API_URL}/api/v1/admin/analytics`
- Added `credentials: "include"` for cookie-based auth

## Testing

After updating CORS, test the admin panel:

1. Open: https://creatives.bimoraai.com/admin
2. Login with admin credentials: dev@photogenius.local / password123
3. Overview tab should load with all analytics
4. Check browser console for any errors

## Alternative: Manual CORS Check

If you want to verify the current CORS setting without editing:
```bash
ssh ubuntu@43.204.223.51
grep ALLOWED_ORIGINS /home/ubuntu/PhotoGenius-AI/apps/api/.env.local
```
