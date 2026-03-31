# Invoke Orchestrator v2 (POST /orchestrate/v2) - no curl quoting issues
# Usage: .\invoke-orchestrate-v2.ps1 -ApiUrl "https://xxx.../Prod/orchestrate/v2" [-Prompt "your prompt"] [-Steps 30]
# Note: API Gateway times out at ~29s. If you see "Endpoint request timed out", SageMaker is still running; use -Steps 20 for faster response or callback_url for long runs.
param(
    [Parameter(Mandatory = $true)]
    [string]$ApiUrl,
    [string]$Prompt = "cinematic portrait, ultra realistic, studio lighting",
    [int]$Steps = 30,
    [int]$Seed = $null
)
$body = @{ prompt = $Prompt; steps = $Steps }
if ($null -ne $Seed) { $body.seed = $Seed }
$json = $body | ConvertTo-Json -Compress
try {
    Invoke-RestMethod -Uri $ApiUrl -Method Post -ContentType "application/json" -Body $json -TimeoutSec 120
} catch {
    if ($_.Exception.Message -match "timed out") {
        Write-Host "Request timed out (API Gateway limit ~29s). Try -Steps 20 or use callback_url for long runs." -ForegroundColor Yellow
    }
    throw
}
