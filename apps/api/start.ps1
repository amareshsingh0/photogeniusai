# PhotoGenius API — Safe Restart Script
Write-Host "Starting PhotoGenius API..." -ForegroundColor Cyan

# Kill any process on port 8003
$pid8003 = (netstat -ano | Select-String ":8003 " | ForEach-Object { ($_ -split "\s+")[-1] } | Select-Object -First 1)
if ($pid8003) {
    Write-Host "Killing old process on port 8003 (PID: $pid8003)..." -ForegroundColor Yellow
    Stop-Process -Id $pid8003 -Force -ErrorAction SilentlyContinue
    Start-Sleep -Seconds 2
}

# Clear pyc cache
Write-Host "Clearing Python cache..." -ForegroundColor Yellow
Get-ChildItem -Path "." -Recurse -Filter "*.pyc" | Remove-Item -Force -ErrorAction SilentlyContinue
Get-ChildItem -Path "." -Recurse -Filter "__pycache__" | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue

# Start server
Write-Host "Starting uvicorn on port 8003..." -ForegroundColor Green
Set-Location "$PSScriptRoot"
uvicorn app.main:app --host 0.0.0.0 --port 8003 --env-file .env.local --reload
