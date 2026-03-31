-- Script to fix safety_audit_logs table structure
-- Run this if the table exists but has wrong structure

-- Option 1: Drop and recreate (WILL DELETE ALL DATA)
-- DROP TABLE IF EXISTS safety_audit_logs CASCADE;

-- Option 2: Check current structure
SELECT column_name, data_type, is_nullable
FROM information_schema.columns
WHERE table_schema = 'public' 
AND table_name = 'safety_audit_logs'
ORDER BY ordinal_position;

-- Option 3: If table is empty or you want to recreate it:
-- DROP TABLE IF EXISTS safety_audit_logs CASCADE;
-- Then run: alembic upgrade head
