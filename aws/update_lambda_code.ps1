# PhotoGenius AI - Update Lambda Function Code
# Simple script to update Lambda code directly

param([string]$Environment = "dev")

Write-Host "Updating Lambda Functions for Environment: $Environment"

# Functions to update
$functions = @(
    @{Name="photogenius-orchestrator-$Environment"; Dir="lambda/orchestrator"},
    @{Name="photogenius-prompt-enhancer-$Environment"; Dir="lambda/prompt_enhancer"},
    @{Name="photogenius-generation-$Environment"; Dir="lambda/generation"},
    @{Name="photogenius-post-processor-$Environment"; Dir="lambda/post_processor"},
    @{Name="photogenius-safety-$Environment"; Dir="lambda/safety"},
    @{Name="photogenius-training-$Environment"; Dir="lambda/training"},
    @{Name="photogenius-refinement-$Environment"; Dir="lambda/refinement"}
)

$successCount = 0
$failedCount = 0

foreach ($func in $functions) {
    Write-Host ""
    Write-Host "--- Processing: $($func.Name) ---"

    $directory = $func.Dir
    if (!(Test-Path $directory)) {
        Write-Host "  WARNING: Directory not found: $directory"
        $failedCount++
        continue
    }

    Write-Host "  Packaging code..."
    Push-Location $directory
    $zipPath = "../../temp_$($func.Name).zip"

    if (Test-Path $zipPath) {
        Remove-Item $zipPath -Force
    }

    Compress-Archive -Path * -DestinationPath $zipPath -Force
    Pop-Location

    $zipSize = (Get-Item $zipPath).Length / 1KB
    Write-Host "  Package created: $([math]::Round($zipSize, 2)) KB"

    Write-Host "  Updating Lambda function..."
    try {
        $result = aws lambda update-function-code `
            --function-name $func.Name `
            --zip-file "fileb://$zipPath" `
            --output json 2>&1

        if ($LASTEXITCODE -eq 0) {
            $data = $result | ConvertFrom-Json
            Write-Host "  SUCCESS! Version: $($data.Version)"
            $successCount++
        } else {
            Write-Host "  FAILED: $result"
            $failedCount++
        }
    } catch {
        Write-Host "  ERROR: $_"
        $failedCount++
    }

    # Cleanup
    Remove-Item $zipPath -ErrorAction SilentlyContinue
}

Write-Host ""
Write-Host "=================================="
Write-Host "SUMMARY:"
Write-Host "  Success: $successCount"
Write-Host "  Failed: $failedCount"
Write-Host "  Total: $($functions.Count)"
Write-Host "=================================="

if ($successCount -gt 0) {
    Write-Host ""
    Write-Host "Lambda functions updated successfully!"
    Write-Host ""
    Write-Host "Test with:"
    Write-Host "  aws lambda invoke --function-name photogenius-orchestrator-$Environment --payload file://test_payload.json response.json"
}
