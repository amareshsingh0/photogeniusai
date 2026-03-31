# Cloud Migration Script for PhotoGenius AI
# Usage: .\scripts\migrate-to-cloud.ps1

Write-Host "🚀 PhotoGenius AI - Cloud Migration Guide" -ForegroundColor Green
Write-Host ""

Write-Host "📊 Current Resource Usage:" -ForegroundColor Yellow
Write-Host "  - AI Service: 8-16GB RAM + GPU" -ForegroundColor Red
Write-Host "  - PostgreSQL: 2-4GB RAM + 5-10GB Disk" -ForegroundColor Yellow
Write-Host "  - Redis: 500MB-2GB RAM" -ForegroundColor Yellow
Write-Host "  - Web/API: 500MB-1GB RAM" -ForegroundColor Green
Write-Host ""

Write-Host "🎯 Recommended Migration Order:" -ForegroundColor Cyan
Write-Host ""
Write-Host "1️⃣  AI Service → Modal.com (GPU)" -ForegroundColor Green
Write-Host "    Cost: ~$0.50-2/hour (only when generating)" -ForegroundColor Gray
Write-Host "    Impact: Frees 8-16GB RAM + GPU" -ForegroundColor Gray
Write-Host ""
Write-Host "2️⃣  PostgreSQL → Supabase (Free tier available)" -ForegroundColor Green
Write-Host "    Cost: FREE (up to 500MB) or $25/month" -ForegroundColor Gray
Write-Host "    Impact: Frees 2-4GB RAM + 5-10GB Disk" -ForegroundColor Gray
Write-Host ""
Write-Host "3️⃣  Redis → Upstash (Free tier available)" -ForegroundColor Green
Write-Host "    Cost: FREE (up to 10K requests/day)" -ForegroundColor Gray
Write-Host "    Impact: Frees 500MB-2GB RAM" -ForegroundColor Gray
Write-Host ""
Write-Host "4️⃣  Web/API → Keep local OR deploy to Vercel/Railway" -ForegroundColor Yellow
Write-Host "    Cost: FREE (Vercel) or $5-20/month (Railway)" -ForegroundColor Gray
Write-Host ""

Write-Host "📝 Quick Start:" -ForegroundColor Cyan
Write-Host ""
Write-Host "Step 1: Deploy AI Service to Modal" -ForegroundColor Yellow
Write-Host "  pip install modal" -ForegroundColor White
Write-Host "  modal token new" -ForegroundColor White
Write-Host "  cd apps/ai-service" -ForegroundColor White
Write-Host "  modal deploy modal_app.py" -ForegroundColor White
Write-Host ""
Write-Host "Step 2: Setup Supabase Database" -ForegroundColor Yellow
Write-Host "  1. Go to https://supabase.com" -ForegroundColor White
Write-Host "  2. Create new project" -ForegroundColor White
Write-Host "  3. Copy connection string" -ForegroundColor White
Write-Host "  4. Update apps/api/.env.local" -ForegroundColor White
Write-Host ""
Write-Host "Step 3: Setup Upstash Redis" -ForegroundColor Yellow
Write-Host "  1. Go to https://upstash.com" -ForegroundColor White
Write-Host "  2. Create Redis database" -ForegroundColor White
Write-Host "  3. Copy connection URL" -ForegroundColor White
Write-Host "  4. Update apps/api/.env.local" -ForegroundColor White
Write-Host ""

Write-Host "📚 Full Guide: docs/CLOUD_MIGRATION_GUIDE.md" -ForegroundColor Cyan
Write-Host ""

$choice = Read-Host "Do you want to open the migration guide? (y/n)"
if ($choice -eq "y" -or $choice -eq "Y") {
    Start-Process "docs/CLOUD_MIGRATION_GUIDE.md"
}
