# PhotoGenius AI - Deploy Lambda Functions
param([string]$Env = "dev")

$ErrorActionPreference = "Stop"
$scriptDir = $PSScriptRoot

Write-Host "Updating Lambda Functions: $Env"
Write-Host ""

# Get absolute paths
$awsDir = $scriptDir
$tempDir = Join-Path $scriptDir "temp"

# Create temp directory
if (!(Test-Path $tempDir)) {
    New-Item -ItemType Directory -Path $tempDir | Out-Null
}

# Functions configuration
$functions = @(
    @{Name="photogenius-orchestrator-$Env"; Dir="lambda\orchestrator"},
    @{Name="photogenius-prompt-enhancer-$Env"; Dir="lambda\prompt_enhancer"},
    @{Name="photogenius-generation-$Env"; Dir="lambda\generation"},
    @{Name="photogenius-post-processor-$Env"; Dir="lambda\post_processor"},
    @{Name="photogenius-safety-$Env"; Dir="lambda\safety"}
)

$success = 0
$failed = 0

foreach ($func in $functions) {
    Write-Host "--- $($func.Name) ---"

    $sourceDir = Join-Path $awsDir $func.Dir
    if (!(Test-Path $sourceDir)) {
        Write-Host "  SKIP: Directory not found" -ForegroundColor Yellow
        $failed++
        continue
    }

    # Create zip file
    $zipFile = Join-Path $tempDir "$($func.Name).zip"
    if (Test-Path $zipFile) {
        Remove-Item $zipFile -Force
    }

    Write-Host "  Packaging..."
    Push-Location $sourceDir
    Compress-Archive -Path * -DestinationPath $zipFile -Force
    Pop-Location

    if (!(Test-Path $zipFile)) {
        Write-Host "  ERROR: Failed to create zip" -ForegroundColor Red
        $failed++
        continue
    }

    $size = [math]::Round((Get-Item $zipFile).Length / 1KB, 2)
    Write-Host "  Package: $size KB"

    # Update Lambda
    Write-Host "  Updating..."
    $result = aws lambda update-function-code `
        --function-name $func.Name `
        --zip-file "fileb://$zipFile" `
        --output json 2>&1

    if ($LASTEXITCODE -eq 0) {
        $data = $result | ConvertFrom-Json
        Write-Host "  SUCCESS - Version: $($data.Version)" -ForegroundColor Green
        $success++
    } else {
        Write-Host "  FAILED: $result" -ForegroundColor Red
        $failed++
    }

    Write-Host ""
}

# Cleanup
Write-Host "Cleaning up..."
Remove-Item $tempDir -Recurse -Force -ErrorAction SilentlyContinue

# Summary
Write-Host "================================"
Write-Host "Success: $success | Failed: $failed"
Write-Host "================================"

if ($success -gt 0) {
    Write-Host ""
    Write-Host "Lambda functions updated!" -ForegroundColor Green
}
