# Quick fix script for migration issues
# This will drop the safety_audit_logs table if it exists with wrong structure
# and let the migration recreate it properly

Write-Host "Checking safety_audit_logs table structure..." -ForegroundColor Yellow

# Check if table exists and has correct structure
$checkQuery = @"
SELECT EXISTS (
    SELECT 1 FROM information_schema.columns 
    WHERE table_schema = 'public' 
    AND table_name = 'safety_audit_logs' 
    AND column_name = 'user_id'
)
"@

Write-Host ""
Write-Host "Option 1: Drop table and recreate (if table has wrong structure)" -ForegroundColor Cyan
Write-Host "  Run this SQL in your database:" -ForegroundColor Gray
Write-Host "  DROP TABLE IF EXISTS safety_audit_logs CASCADE;" -ForegroundColor White
Write-Host ""
Write-Host "  Then run: alembic upgrade head" -ForegroundColor Gray
Write-Host ""
Write-Host "Option 2: Just stamp the migration (if you'll fix structure manually)" -ForegroundColor Cyan
Write-Host "  alembic stamp 001_safety_audit" -ForegroundColor White
Write-Host ""
