# Invoke Orchestrator v2 Lambda DIRECTLY (bypass API Gateway 29s timeout)
# Usage: .\invoke-lambda-direct.ps1 -Prompt "your prompt" [-Steps 30] [-Region us-east-1]
param(
    [string]$Prompt = "cinematic portrait, ultra realistic, studio lighting",
    [int]$Steps = 30,
    [string]$Region = "us-east-1",
    [string]$FunctionName = "photogenius-orchestrator-v2-dev"
)
$innerBody = @{ prompt = $Prompt; steps = $Steps } | ConvertTo-Json -Compress
$payload = @{ body = $innerBody } | ConvertTo-Json -Compress
# Write payload to temp file (avoids escaping issues)
$payloadFile = [System.IO.Path]::GetTempFileName()
$payload | Out-File -FilePath $payloadFile -Encoding utf8 -NoNewline

$outFile = [System.IO.Path]::GetTempFileName()
Write-Host "Invoking Lambda directly (no API Gateway timeout)..." -ForegroundColor Cyan
Write-Host "Function: $FunctionName | Region: $Region | Steps: $Steps" -ForegroundColor Gray
Write-Host "Prompt: $Prompt" -ForegroundColor Gray

$result = aws lambda invoke `
    --function-name $FunctionName `
    --region $Region `
    --cli-read-timeout 300 `
    --payload "fileb://$payloadFile" `
    $outFile 2>&1

Remove-Item $payloadFile -Force -ErrorAction SilentlyContinue

if ($LASTEXITCODE -ne 0) {
    Write-Host "Lambda invoke failed: $result" -ForegroundColor Red
    exit 1
}

$response = Get-Content $outFile -Raw | ConvertFrom-Json
Remove-Item $outFile -Force

if ($response.statusCode -eq 200) {
    $body = $response.body | ConvertFrom-Json
    Write-Host "`n=== SUCCESS ===" -ForegroundColor Green
    Write-Host "Quality Tier: $($body.metadata.quality_tier)"
    Write-Host "Total Time: $($body.metadata.total_time)s"
    if ($body.metadata.image_url) {
        Write-Host "Image URL: $($body.metadata.image_url)" -ForegroundColor Cyan
    }
    if ($body.images.final) {
        $preview = $body.images.final.Substring(0, [Math]::Min(100, $body.images.final.Length))
        Write-Host "Final image (base64 preview): $preview..." -ForegroundColor Gray
    }
    # Return full response for piping
    $body | ConvertTo-Json -Depth 10
} else {
    Write-Host "Error: $($response.body)" -ForegroundColor Red
    $response | ConvertTo-Json
}
