# Start all PhotoGenius AI services
# Usage: .\scripts\start-services.ps1

Write-Host "Starting PhotoGenius AI Services..." -ForegroundColor Green

# Navigate to project root
$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $projectRoot

# Stop any existing containers
Write-Host ""
Write-Host "Stopping existing containers..." -ForegroundColor Yellow
docker compose -f infra/docker/docker-compose.dev.yml down 2>$null

# Start infrastructure first (postgres + redis)
Write-Host ""
Write-Host "Starting infrastructure (postgres + redis)..." -ForegroundColor Yellow
docker compose -f infra/docker/docker-compose.dev.yml up -d postgres redis

# Wait for health checks
Write-Host "Waiting for database and redis to be healthy..." -ForegroundColor Yellow
Start-Sleep -Seconds 10

# Check health
$postgresHealth = docker inspect --format='{{.State.Health.Status}}' photogenius-postgres 2>$null
$redisHealth = docker inspect --format='{{.State.Health.Status}}' photogenius-redis 2>$null

if ($postgresHealth -eq "healthy" -and $redisHealth -eq "healthy") {
    Write-Host "✓ Infrastructure is healthy" -ForegroundColor Green
    
    # Start application services
    Write-Host ""
    Write-Host "Starting application services (web + api)..." -ForegroundColor Yellow
    Write-Host "AI Service runs on Modal.com (cloud) - no local container needed" -ForegroundColor Cyan
    Write-Host "This may take several minutes on first build..." -ForegroundColor Yellow
    
    docker compose -f infra/docker/docker-compose.dev.yml up -d --build web api
    
    Write-Host ""
    Write-Host "Services starting..." -ForegroundColor Green
    Write-Host "Check status with: docker compose -f infra/docker/docker-compose.dev.yml ps" -ForegroundColor Cyan
    Write-Host "View logs with: docker compose -f infra/docker/docker-compose.dev.yml logs -f [service-name]" -ForegroundColor Cyan
} else {
    Write-Host "✗ Infrastructure not healthy. Please check logs:" -ForegroundColor Red
    Write-Host "  docker compose -f infra/docker/docker-compose.dev.yml logs postgres redis" -ForegroundColor Yellow
}

# Show status
Write-Host ""
Write-Host "Current service status:" -ForegroundColor Cyan
docker compose -f infra/docker/docker-compose.dev.yml ps
