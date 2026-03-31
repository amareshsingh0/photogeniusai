import { createClient } from "@supabase/supabase-js";

/**
 * Server-only Supabase client with service role (bypass RLS).
 * Use for uploads, admin operations. Requires SUPABASE_SECRET_KEY.
 */
export function createAdminClient() {
  const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
  const key = process.env.SUPABASE_SECRET_KEY;
  if (!url || !key) {
    throw new Error("Missing NEXT_PUBLIC_SUPABASE_URL or SUPABASE_SECRET_KEY");
  }
  return createClient(url, key);
}
