# PhotoGenius GPU Management Script
# Manages BOTH SageMaker endpoints with a single command
#
# Usage:
#   .\gpu.ps1 start   - Start BOTH endpoints (generation + orchestrator)
#   .\gpu.ps1 stop    - Stop BOTH endpoints (save money!)
#   .\gpu.ps1 status  - Check status of both endpoints

param(
    [Parameter(Position=0)]
    [ValidateSet("start", "stop", "status", "")]
    [string]$Action = "status"
)

$REGION = "us-east-1"

# Endpoint names
$GEN_ENDPOINT    = "photogenius-generation-dev"
$ORCH_ENDPOINT   = "photogenius-orchestrator"

# Config prefixes (both use dynamic latest config)
$GEN_CONFIG_PREFIX  = "photogenius-generation"
$ORCH_CONFIG_PREFIX = "photogenius-orchestrator"

function Get-EndpointStatus($name) {
    $r = aws sagemaker describe-endpoint --endpoint-name $name --region $REGION 2>&1
    if ($LASTEXITCODE -ne 0) { return $null }
    ($r | ConvertFrom-Json).EndpointStatus
}

function Get-StatusColor($status) {
    switch ($status) {
        "InService"  { return "Green" }
        "Creating"   { return "Yellow" }
        "Updating"   { return "Yellow" }
        "Deleting"   { return "DarkYellow" }
        "Failed"     { return "Red" }
        $null        { return "Gray" }
        default      { return "White" }
    }
}

function Show-Status {
    Write-Host ""
    Write-Host "=== PhotoGenius GPU Status ===" -ForegroundColor Cyan

    $genStatus  = Get-EndpointStatus $GEN_ENDPOINT
    $orchStatus = Get-EndpointStatus $ORCH_ENDPOINT

    $genDisplay  = if ($genStatus)  { $genStatus }  else { "NOT RUNNING" }
    $orchDisplay = if ($orchStatus) { $orchStatus } else { "NOT RUNNING" }

    Write-Host ""
    Write-Host "  GPU1 - Generation  ($GEN_ENDPOINT)" -ForegroundColor White
    Write-Host "         Status: " -NoNewline
    Write-Host $genDisplay -ForegroundColor (Get-StatusColor $genStatus)
    Write-Host "         Instance: ml.g5.2xlarge  |  Models: PixArt-Sigma + FLUX + CLIP + ESRGAN" -ForegroundColor DarkGray

    Write-Host ""
    Write-Host "  GPU2 - Orchestrator ($ORCH_ENDPOINT)" -ForegroundColor White
    Write-Host "         Status: " -NoNewline
    Write-Host $orchDisplay -ForegroundColor (Get-StatusColor $orchStatus)
    Write-Host "         Instance: ml.g5.2xlarge  |  Models: Qwen2-1.5B + Llama-3.1-8B" -ForegroundColor DarkGray

    Write-Host ""

    $bothRunning = ($genStatus -eq "InService") -and ($orchStatus -eq "InService")
    $noneRunning = (-not $genStatus) -and (-not $orchStatus)

    if ($bothRunning) {
        Write-Host "  Both endpoints InService. Estimated cost: ~$3.70/hr ($1.85/hr x2)" -ForegroundColor Green
    } elseif ($noneRunning) {
        Write-Host "  No endpoints running. Cost: $0.00/hr" -ForegroundColor Gray
        Write-Host "  Start with: .\gpu.ps1 start" -ForegroundColor DarkGray
    } else {
        Write-Host "  Partial deployment. Cost: ~$1.85/hr" -ForegroundColor Yellow
    }
    Write-Host ""
}

function Get-LatestConfig($prefix) {
    # List all configs containing the prefix, return latest by creation time
    $r = aws sagemaker list-endpoint-configs --region $REGION --name-contains $prefix 2>&1
    if ($LASTEXITCODE -ne 0) { return $null }

    $configs = ($r | ConvertFrom-Json).EndpointConfigs
    if (-not $configs -or $configs.Count -eq 0) { return $null }

    # Sort by creation time descending, pick first
    $latest = $configs | Sort-Object CreationTime -Descending | Select-Object -First 1
    return $latest.EndpointConfigName
}

function Start-Endpoint($endpointName, $configName) {
    $status = Get-EndpointStatus $endpointName

    if ($status) {
        Write-Host "  $endpointName already exists ($status) - skipping" -ForegroundColor Yellow
        return
    }

    if (-not $configName) {
        Write-Host "  ERROR: No endpoint config found for $endpointName" -ForegroundColor Red
        return
    }

    Write-Host "  Creating $endpointName from config: $configName" -ForegroundColor White

    aws sagemaker create-endpoint `
        --endpoint-name $endpointName `
        --endpoint-config-name $configName `
        --region $REGION 2>&1 | Out-Null

    if ($LASTEXITCODE -eq 0) {
        Write-Host "  Started: $endpointName" -ForegroundColor Green
    } else {
        Write-Host "  ERROR starting $endpointName - check AWS console" -ForegroundColor Red
    }
}

function Start-All {
    Write-Host ""
    Write-Host "=== Starting PhotoGenius GPU Endpoints ===" -ForegroundColor Cyan
    Write-Host "  Both instances: ml.g5.2xlarge (A10G 24GB)" -ForegroundColor DarkGray
    Write-Host "  This takes 10-15 minutes..." -ForegroundColor DarkGray
    Write-Host ""

    # Find latest configs dynamically
    $genConfig  = Get-LatestConfig $GEN_CONFIG_PREFIX
    $orchConfig = Get-LatestConfig $ORCH_CONFIG_PREFIX

    if (-not $genConfig) {
        Write-Host "  WARNING: No generation config found. Was it ever deployed?" -ForegroundColor Yellow
        Write-Host "  Run: cd aws\sagemaker && python deploy_endpoint.py" -ForegroundColor DarkGray
    }
    if (-not $orchConfig) {
        Write-Host "  WARNING: No orchestrator config found. Was it ever deployed?" -ForegroundColor Yellow
        Write-Host "  Run: cd aws\sagemaker && python deploy_endpoint.py" -ForegroundColor DarkGray
    }

    Write-Host "GPU1 - Generation:" -ForegroundColor Cyan
    if ($genConfig) {
        Write-Host "  Using config: $genConfig" -ForegroundColor DarkGray
        Start-Endpoint $GEN_ENDPOINT $genConfig
    } else {
        Write-Host "  Skipped (no config found)" -ForegroundColor DarkYellow
    }

    Write-Host ""
    Write-Host "GPU2 - Orchestrator:" -ForegroundColor Cyan
    if ($orchConfig) {
        Write-Host "  Using config: $orchConfig" -ForegroundColor DarkGray
        Start-Endpoint $ORCH_ENDPOINT $orchConfig
    } else {
        Write-Host "  Skipped (no config found)" -ForegroundColor DarkYellow
    }

    Write-Host ""
    Write-Host "Check progress: .\gpu.ps1 status" -ForegroundColor Cyan
    Write-Host ""
}

function Stop-Endpoint($endpointName) {
    $status = Get-EndpointStatus $endpointName

    if (-not $status) {
        Write-Host "  $endpointName not running - skipping" -ForegroundColor DarkGray
        return
    }

    if ($status -eq "Deleting") {
        Write-Host "  $endpointName already deleting" -ForegroundColor DarkYellow
        return
    }

    Write-Host "  Deleting $endpointName ($status)..." -ForegroundColor Yellow

    aws sagemaker delete-endpoint `
        --endpoint-name $endpointName `
        --region $REGION 2>&1 | Out-Null

    if ($LASTEXITCODE -eq 0) {
        Write-Host "  Deleted: $endpointName" -ForegroundColor Green
    } else {
        Write-Host "  ERROR deleting $endpointName" -ForegroundColor Red
    }
}

function Stop-All {
    Write-Host ""
    Write-Host "=== Stopping PhotoGenius GPU Endpoints ===" -ForegroundColor Cyan
    Write-Host ""

    Write-Host "GPU1 - Generation:" -ForegroundColor Cyan
    Stop-Endpoint $GEN_ENDPOINT

    Write-Host ""
    Write-Host "GPU2 - Orchestrator:" -ForegroundColor Cyan
    Stop-Endpoint $ORCH_ENDPOINT

    Write-Host ""
    Write-Host "All endpoints stopped. GPU cost: $0.00/hr" -ForegroundColor Green
    Write-Host ""
}

# Main
switch ($Action) {
    "start"  { Start-All }
    "stop"   { Stop-All }
    "status" { Show-Status }
    ""       { Show-Status }
}
