# Clerk Webhook Setup for PhotoGenius AI

## ✅ Credentials Already Configured

All Clerk credentials are already properly set up in your `.env.local` files:

### Frontend (`apps/web/.env.local`)
```bash
NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=pk_test_dG9sZXJhbnQtZG9nLTI4LmNsZXJrLmFjY291bnRzLmRldiQ
CLERK_SECRET_KEY=sk_test_a4kjikWGmQjqybn8cykySbbjVP1yRUiXot4t7ru2p3
CLERK_WEBHOOK_SECRET=whsec_OMtQ55Luc2kp6lW/pq/j6f8LfsH2t57E
```

### Backend (`apps/api/.env.local`)
```bash
CLERK_SECRET_KEY=sk_test_a4kjikWGmQjqybn8cykySbbjVP1yRUiXot4t7ru2p3
```

---

## 🔧 Update Required: Webhook Endpoint URL

### Current Issue
Your Clerk dashboard webhook is configured for:
```
http://localhost:3000/api/webhooks/clerk
```

But your app is running on:
```
http://localhost:3002
```

### How to Fix

1. **Go to Clerk Dashboard** (where you showed the screenshot):
   - Navigate to: **Configure → Endpoints**
   - Or direct link: `dashboard.clerk.com/apps/app_38jzUl26o3mvtEUolkbRe6FbnZ77/instances/ins_38jzUk9TAraaZPrSUNXJayCmRmK/webhooks`

2. **Update the Endpoint**:
   - Click on the existing endpoint: `http://localhost:3000/api/webhooks/clerk`
   - Change the URL to: `http://localhost:3002/api/webhooks/clerk`
   - Or click "Add Endpoint" and create a new one with port `3002`
   - Make sure to select these events:
     - ✅ `user.created`
     - ✅ `user.updated`
     - ✅ `user.deleted`

3. **Save** the changes

---

## 📍 Webhook Endpoint Details

| Setting | Value |
|---------|-------|
| **URL** | `http://localhost:3002/api/webhooks/clerk` |
| **Method** | POST |
| **Events** | `user.created`, `user.updated`, `user.deleted` |
| **Secret** | `whsec_OMtQ55Luc2kp6lW/pq/j6f8LfsH2t57E` (already in .env) |

---

## ✅ What the Webhook Does

When users sign up/update/delete their accounts via Clerk, the webhook automatically:

1. **`user.created`**: Creates user record in your Supabase database
2. **`user.updated`**: Updates user info (name, email, profile image)
3. **`user.deleted`**: Logs user deletion (cleanup can be added)

The webhook handler is at: `apps/web/app/api/webhooks/clerk/route.ts`

---

## 🧪 Testing the Webhook

After updating the URL in Clerk dashboard:

1. **Test from Clerk Dashboard**:
   - In the webhook settings, click "Send test event"
   - Should show successful response

2. **Test with Real Signup**:
   - Go to: `http://localhost:3002/signup`
   - Create a test account
   - Check your database - user should be created automatically

---

## 🔐 Security Notes

- ✅ Webhook uses `svix` signature verification
- ✅ `CLERK_WEBHOOK_SECRET` validates all incoming requests
- ✅ Invalid signatures are rejected with 400 error

---

## 📝 Summary

**Action Required:**
- [ ] Update Clerk webhook endpoint URL from port `3000` to `3002`

**Already Done:**
- [x] Clerk credentials configured in `.env.local`
- [x] Webhook handler implemented
- [x] Database integration ready
- [x] Signature verification enabled

**After Updating:**
Website will automatically sync Clerk users to your Supabase database!

---

**Last Updated:** February 8, 2026
**Status:** Ready - Just update webhook URL in Clerk dashboard
