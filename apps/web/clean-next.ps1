# Clean Next.js build cache
# Usage: .\clean-next.ps1

Write-Host "🧹 Cleaning Next.js cache..." -ForegroundColor Cyan

# Stop any running Next.js processes
Write-Host "Stopping Node processes..." -ForegroundColor Yellow
Get-Process | Where-Object {$_.ProcessName -like "*node*"} | Stop-Process -Force -ErrorAction SilentlyContinue
Start-Sleep -Seconds 2

# Remove .next folder
if (Test-Path .next) {
    Write-Host "Removing .next folder..." -ForegroundColor Yellow
    Remove-Item -Recurse -Force .next -ErrorAction SilentlyContinue
    Write-Host "✅ .next folder removed" -ForegroundColor Green
} else {
    Write-Host "✅ .next folder doesn't exist" -ForegroundColor Green
}

# Remove node_modules/.cache if exists
if (Test-Path "node_modules\.cache") {
    Write-Host "Removing node_modules/.cache..." -ForegroundColor Yellow
    Remove-Item -Recurse -Force "node_modules\.cache" -ErrorAction SilentlyContinue
    Write-Host "✅ Cache cleared" -ForegroundColor Green
}

Write-Host "✨ Done! You can now run 'pnpm dev' again" -ForegroundColor Green
