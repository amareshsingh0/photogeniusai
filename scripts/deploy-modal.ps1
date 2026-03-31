# Deploy all Modal services for PhotoGenius AI
# Run this script from the project root directory

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "  PhotoGenius AI - Modal Deployment" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""

# Check if Modal is installed and authenticated
Write-Host "[1/3] Checking Modal CLI..." -ForegroundColor Yellow
try {
    $modalVersion = modal --version 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-Host "ERROR: Modal CLI not found. Install with: pip install modal" -ForegroundColor Red
        exit 1
    }
    Write-Host "  Modal CLI: $modalVersion" -ForegroundColor Green
} catch {
    Write-Host "ERROR: Modal CLI not found. Install with: pip install modal" -ForegroundColor Red
    exit 1
}

# Check Modal authentication
Write-Host "[2/3] Checking Modal authentication..." -ForegroundColor Yellow
try {
    modal token show 2>&1 | Out-Null
    if ($LASTEXITCODE -ne 0) {
        Write-Host "ERROR: Not authenticated. Run: modal token new" -ForegroundColor Red
        exit 1
    }
    Write-Host "  Modal authenticated" -ForegroundColor Green
} catch {
    Write-Host "ERROR: Not authenticated. Run: modal token new" -ForegroundColor Red
    exit 1
}

# Change to ai-pipeline directory
$aiPipelineDir = Join-Path $PSScriptRoot "..\ai-pipeline"
if (!(Test-Path $aiPipelineDir)) {
    Write-Host "ERROR: ai-pipeline directory not found" -ForegroundColor Red
    exit 1
}
Push-Location $aiPipelineDir

Write-Host ""
Write-Host "[3/3] Deploying Modal services..." -ForegroundColor Yellow
Write-Host ""

# Define services in dependency order
$services = @(
    @{ name = "Safety Service"; file = "services/safety_service.py" },
    @{ name = "Quality Scorer"; file = "services/quality_scorer.py" },
    @{ name = "Generation Service"; file = "services/generation_service.py" },
    @{ name = "Identity Engine V2"; file = "services/identity_engine_v2.py" },
    @{ name = "Realtime Engine"; file = "services/realtime_engine.py" },
    @{ name = "Creative Engine"; file = "services/creative_engine.py" },
    @{ name = "Finish Engine"; file = "services/finish_engine.py" },
    @{ name = "Refinement Engine"; file = "services/refinement_engine.py" },
    @{ name = "Composition Engine"; file = "services/composition_engine.py" },
    @{ name = "Ultra High-Res Engine"; file = "services/ultra_high_res_engine.py" },
    @{ name = "LoRA Trainer"; file = "services/lora_trainer.py" },
    @{ name = "Orchestrator"; file = "services/orchestrator.py" }
)

$successCount = 0
$failCount = 0

foreach ($service in $services) {
    Write-Host "  Deploying $($service.name)..." -ForegroundColor Cyan -NoNewline

    try {
        $output = modal deploy $service.file 2>&1
        if ($LASTEXITCODE -eq 0) {
            Write-Host " OK" -ForegroundColor Green
            $successCount++
        } else {
            Write-Host " FAILED" -ForegroundColor Red
            Write-Host "    Error: $output" -ForegroundColor Red
            $failCount++
        }
    } catch {
        Write-Host " ERROR" -ForegroundColor Red
        Write-Host "    Exception: $_" -ForegroundColor Red
        $failCount++
    }
}

Pop-Location

Write-Host ""
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "  Deployment Summary" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "  Successful: $successCount" -ForegroundColor Green
Write-Host "  Failed: $failCount" -ForegroundColor $(if ($failCount -eq 0) { "Green" } else { "Red" })
Write-Host ""

if ($failCount -eq 0) {
    Write-Host "All services deployed successfully!" -ForegroundColor Green
    Write-Host ""
    Write-Host "Modal Endpoint URLs:" -ForegroundColor Yellow
    Write-Host "  Run 'modal app list' to see all deployed apps" -ForegroundColor Gray
    Write-Host ""
    Write-Host "Expected endpoints (replace cn149 with your username):" -ForegroundColor Yellow
    Write-Host "  Safety:     https://cn149--photogenius-safety--check-prompt-safety-web.modal.run" -ForegroundColor Gray
    Write-Host "  Generation: https://cn149--photogenius-generation--generate-images-web.modal.run" -ForegroundColor Gray
    Write-Host "  Refinement: https://cn149--photogenius-refinement-engine--refine-web.modal.run" -ForegroundColor Gray
    Write-Host "  Training:   https://cn149--photogenius-lora-trainer--train-lora-web.modal.run" -ForegroundColor Gray
} else {
    Write-Host "Some services failed to deploy. Check the errors above." -ForegroundColor Red
    exit 1
}
