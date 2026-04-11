# Admin Dashboard Setup Guide

## Overview
Comprehensive admin panel with full system control - user management, analytics, generation history, and system settings.

**Access**: `http://localhost:3002/admin` (local) or `https://creatives.bimoraai.com/admin` (production)

## Features

### 1. **Overview Tab** - System Analytics
- **Stats Cards**: Total users, generations, active users, credits used
- **Time-based metrics**: Today, this week, this month
- **Breakdowns**: By quality tier, by bucket
- **User growth charts**: Last 30 days

### 2. **Users Tab** - User Management
- **View all users** with pagination (50 per page)
- **Search** by email or name
- **Edit user**: Name, email, role, credits
- **Delete user**: Remove user and all data
- **User details**: Generation count, join date, role badge

### 3. **Generations Tab** - Generation History
- **View all generations** with pagination
- **Filter** by user, quality tier, bucket
- **Generation details**: Prompt, model used, credits, date
- **Delete generation**: Remove generation and variants

### 4. **Settings Tab** - System Configuration
- **Generation Backend**: Toggle Ideogram, Gemini, BFL, KIE, Pixazo
- **BEAST Architecture**: Master Strategist, Deterministic Layout, Hybrid Quality Critic
- **Quality Settings**: Thresholds, dimension floor, max images, Beast gates
- **API Keys Status**: Check which providers are configured

## Setup Instructions

### 1. Create Admin User

#### Option A: Make existing user admin
```bash
# Make dev user admin
npx tsx scripts/make-admin.ts dev@photogenius.local

# Or make any user admin
npx tsx scripts/make-admin.ts user@example.com
```

#### Option B: Create new admin user
```bash
# First create the user
npx tsx scripts/create-dummy-user.ts

# Then make them admin
npx tsx scripts/make-admin.ts dev@photogenius.local
```

### 2. Database Schema Update (if needed)

If User table doesn't have `role` column, add it:

```sql
-- In Supabase SQL Editor or via Prisma migration
ALTER TABLE "User" ADD COLUMN role TEXT DEFAULT 'USER';
UPDATE "User" SET role = 'ADMIN' WHERE email = 'dev@photogenius.local';
```

Or update your Prisma schema:
```prisma
model User {
  id        String   @id @default(cuid())
  email     String   @unique
  name      String
  role      String   @default("USER") // USER, ADMIN, SUPER_ADMIN
  credits   Int      @default(100)
  // ... other fields
}
```

Then run:
```bash
npx prisma migrate dev --name add_user_role
```

### 3. Test Admin Access

1. **Install dependencies** (if not already):
```bash
cd apps/web
pnpm install
```

2. **Start dev server**:
```bash
pnpm dev
```

3. **Login as admin**:
- Go to: http://localhost:3002/login
- Email: `dev@photogenius.local`
- Password: `password123`

4. **Access admin dashboard**:
- Go to: http://localhost:3002/admin
- If not admin, you'll see "Admin privileges required" error

## API Endpoints

All admin endpoints require admin authentication:

### Users
- `GET /api/admin/users?page=1&limit=50&search=email` - List users
- `PATCH /api/admin/users` - Update user
- `DELETE /api/admin/users?userId=xxx` - Delete user

### Analytics
- `GET /api/admin/analytics` - Get system analytics

### Generations
- `GET /api/admin/generations?page=1&limit=50` - List generations
- `DELETE /api/admin/generations?generationId=xxx` - Delete generation

### Settings
- `GET /api/admin/settings` - Get system settings
- `PATCH /api/admin/settings` - Update settings

## Production Deployment

### 1. Create Admin User on Production

SSH into production server:
```bash
ssh ubuntu@13.234.5.134
cd /home/ubuntu/PhotoGenius-AI

# Create admin user
npx tsx scripts/make-admin.ts admin@yourdomain.com
```

### 2. Access Admin Panel

Production URL: `https://creatives.bimoraai.com/admin`

### 3. Security Notes

**IMPORTANT**:
- ✅ Admin routes are protected by `requireAdmin()` middleware
- ✅ Only users with `role = ADMIN` or `SUPER_ADMIN` can access
- ✅ In development, `dev@photogenius.local` is auto-admin
- ✅ JWT tokens required for authentication
- ⚠️ Consider adding IP whitelist for production admin access
- ⚠️ Enable audit logging for admin actions (future enhancement)

## Roles

- **USER**: Normal user (default)
- **ADMIN**: Full admin access (all tabs, all operations)
- **SUPER_ADMIN**: Reserved for future multi-admin management

## Admin Actions

### User Management
- ✅ View all users with search
- ✅ Edit user details (name, email, role, credits)
- ✅ Delete users (⚠️ permanently deletes all user data)
- ✅ View user generation count

### Generation Management
- ✅ View all generations across all users
- ✅ Filter by user, quality tier, bucket
- ✅ Delete generations (⚠️ permanently deletes variants too)

### System Settings
- ✅ Toggle feature flags (Ideogram, Gemini, BEAST features)
- ✅ View quality thresholds
- ✅ Check API key status
- ⚠️ Changes to settings require API server restart

## Troubleshooting

### "Admin privileges required" error
- Check user role: `SELECT role FROM "User" WHERE email = 'your@email.com';`
- Make admin: `npx tsx scripts/make-admin.ts your@email.com`

### Settings not updating
- Settings are read from .env.local file
- Changes require API server restart: `pm2 restart photogenius-api`

### Analytics not loading
- Check database connection in .env
- Verify Prisma client is working: `npx prisma studio`

### 403 Forbidden on admin routes
- JWT token expired or invalid
- Re-login at /login
- Check `auth_token` cookie exists

## Future Enhancements

Planned features:
- 📊 **Advanced Analytics**: Charts, graphs, trends
- 📧 **Email Management**: Send emails to users
- 🔍 **Audit Logs**: Track all admin actions
- 🎨 **Theme Customization**: Dark/light mode toggle
- 📱 **Mobile Responsive**: Better mobile admin experience
- 🔐 **2FA for Admins**: Extra security layer
- 🌍 **IP Whitelist**: Restrict admin access by IP
- 📦 **Bulk Operations**: Bulk user/generation management

## Support

For admin dashboard issues:
- Check logs: `pm2 logs photogenius-web`
- Database issues: `npx prisma studio`
- GitHub Issues: https://github.com/anthropics/photogenius-ai/issues
