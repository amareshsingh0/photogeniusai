# Simple Lambda Code Updater
param([string]$Env = "dev")

Write-Host "🚀 Updating Lambda Functions for Environment: $Env" -ForegroundColor Cyan

# Lambda functions to update
$functions = @(
    @{Name="photogenius-orchestrator-$Env"; Dir="lambda/orchestrator"},
    @{Name="photogenius-prompt-enhancer-$Env"; Dir="lambda/prompt_enhancer"},
    @{Name="photogenius-generation-$Env"; Dir="lambda/generation"},
    @{Name="photogenius-post-processor-$Env"; Dir="lambda/post_processor"},
    @{Name="photogenius-safety-$Env"; Dir="lambda/safety"}
)

$success = 0
$failed = 0

foreach ($func in $functions) {
    Write-Host "`n━━━ $($func.Name) ━━━" -ForegroundColor Yellow

    $dir = $func.Dir
    if (!(Test-Path $dir)) {
        Write-Host "  ⚠ Directory not found: $dir" -ForegroundColor Red
        $failed++
        continue
    }

    Write-Host "  📦 Packaging..." -ForegroundColor Cyan
    Push-Location $dir
    $zipFile = "..\..\temp_$($func.Name).zip"
    if (Test-Path $zipFile) { Remove-Item $zipFile }
    Compress-Archive -Path * -DestinationPath $zipFile -Force
    Pop-Location

    Write-Host "  🚀 Updating Lambda..." -ForegroundColor Cyan
    try {
        aws lambda update-function-code `
            --function-name $func.Name `
            --zip-file "fileb://$zipFile" `
            --output json | Out-Null

        if ($LASTEXITCODE -eq 0) {
            Write-Host "  ✅ Updated successfully!" -ForegroundColor Green
            $success++
        } else {
            Write-Host "  ❌ Update failed" -ForegroundColor Red
            $failed++
        }
    } catch {
        Write-Host "  ❌ Error: $_" -ForegroundColor Red
        $failed++
    }

    Remove-Item $zipFile -ErrorAction SilentlyContinue
}

Write-Host "`n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor DarkGray
Write-Host "✅ Success: $success  ❌ Failed: $failed" -ForegroundColor Cyan
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor DarkGray
