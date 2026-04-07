# Deploy all fixes to production server
# Run this from PowerShell: .\deploy_fixes.ps1

Write-Host "🚀 Deploying fixes to PhotoGenius API..." -ForegroundColor Cyan

$SERVER = "ubuntu@13.200.252.174"
$REMOTE_DIR = "/home/ubuntu/photogenius-api"
$SSH_KEY = "~/.ssh/photogenius.pem"  # Update this path if needed

# Files to deploy
$FILES = @(
    "apps/api/app/services/smart/design_director.py",
    "apps/api/app/services/smart/design_agent_chain.py",
    "apps/api/app/api/v1/endpoints/generate_stream.py"
)

Write-Host "`n📦 Uploading fixed files..." -ForegroundColor Yellow
foreach ($file in $FILES) {
    Write-Host "  → $file" -ForegroundColor Gray
    scp -i $SSH_KEY $file "${SERVER}:${REMOTE_DIR}/$file"
    if ($LASTEXITCODE -ne 0) {
        Write-Host "❌ Failed to upload $file" -ForegroundColor Red
        exit 1
    }
}

Write-Host "`n🔄 Restarting PM2 process..." -ForegroundColor Yellow
ssh -i $SSH_KEY $SERVER @"
cd /home/ubuntu/photogenius-api
pm2 restart photogenius-api
echo ''
echo '📊 Latest logs:'
pm2 logs photogenius-api --lines 20 --nostream
"@

Write-Host "`n✅ Deployment complete!" -ForegroundColor Green
Write-Host "`n🧪 Test generation:" -ForegroundColor Cyan
Write-Host "curl -X POST http://13.200.252.174:8003/api/v1/generate/stream -H 'Content-Type: application/json' -d '{""prompt"": ""gym poster with text TRANSFORM and Join Now"", ""quality"": ""premium""}'"
