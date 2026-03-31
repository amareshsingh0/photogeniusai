# PhotoGenius AI - Development Server Launcher
# Automatically kills existing processes and starts fresh

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "PhotoGenius AI - Development Server" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Add pnpm to PATH for this session
$env:Path += ";C:\Users\dell\AppData\Roaming\npm"

# Kill existing Python processes to free ports
Write-Host "[1/4] Cleaning up existing processes..." -ForegroundColor Yellow
Get-Process python -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
Start-Sleep -Seconds 2
Write-Host "      Done!" -ForegroundColor Green
Write-Host ""

# Kill Node processes
Get-Process node -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
Start-Sleep -Seconds 1

# Generate Prisma client
Write-Host "[2/4] Generating Prisma client..." -ForegroundColor Yellow
Push-Location packages\database
pnpm run build
Pop-Location
Write-Host "      Done!" -ForegroundColor Green
Write-Host ""

Write-Host "[3/4] Starting development servers..." -ForegroundColor Yellow
Write-Host "      This will start:" -ForegroundColor Gray
Write-Host "      - Frontend at http://localhost:3002" -ForegroundColor Gray
Write-Host "      - API at http://localhost:8000" -ForegroundColor Gray
Write-Host "      - AI Service at http://localhost:8001" -ForegroundColor Gray
Write-Host ""

# Run development server
Write-Host "[4/4] Running pnpm dev..." -ForegroundColor Yellow
Write-Host ""

pnpm run dev
