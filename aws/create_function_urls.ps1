# Create Lambda Function URLs for PhotoGenius AI
param([string]$Environment = "dev")

Write-Host "Creating Lambda Function URLs for Environment: $Environment"
Write-Host ""

# Functions that need public URLs
$functions = @(
    "photogenius-orchestrator-$Environment",
    "photogenius-generation-$Environment",
    "photogenius-safety-$Environment",
    "photogenius-prompt-enhancer-$Environment"
)

$urls = @{}

foreach ($funcName in $functions) {
    Write-Host "--- $funcName ---"
    
    # Check if Function URL already exists
    $existing = aws lambda get-function-url-config --function-name $funcName 2>&1
    
    if ($LASTEXITCODE -eq 0) {
        $config = $existing | ConvertFrom-Json
        Write-Host "  Function URL already exists: $($config.FunctionUrl)" -ForegroundColor Yellow
        $urls[$funcName] = $config.FunctionUrl
    } else {
        Write-Host "  Creating Function URL..."
        
        # Create Function URL with CORS
        $result = aws lambda create-function-url-config `
            --function-name $funcName `
            --auth-type NONE `
            --cors '{
                "AllowOrigins": ["*"],
                "AllowMethods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
                "AllowHeaders": ["*"],
                "ExposeHeaders": ["*"],
                "MaxAge": 86400,
                "AllowCredentials": false
            }' `
            --output json 2>&1
        
        if ($LASTEXITCODE -eq 0) {
            $data = $result | ConvertFrom-Json
            Write-Host "  SUCCESS: $($data.FunctionUrl)" -ForegroundColor Green
            $urls[$funcName] = $data.FunctionUrl
            
            # Add resource-based policy to allow public invocation
            Write-Host "  Adding public invoke permission..."
            aws lambda add-permission `
                --function-name $funcName `
                --statement-id FunctionURLAllowPublicAccess `
                --action lambda:InvokeFunctionUrl `
                --principal "*" `
                --function-url-auth-type NONE `
                --output json | Out-Null
            
            if ($LASTEXITCODE -eq 0) {
                Write-Host "  Permission added" -ForegroundColor Green
            }
        } else {
            Write-Host "  FAILED: $result" -ForegroundColor Red
        }
    }
    
    Write-Host ""
}

# Save URLs to file
Write-Host "================================"
Write-Host "FUNCTION URLS:"
Write-Host "================================"

$envContent = @"
# PhotoGenius AI - Lambda Function URLs
# Generated: $(Get-Date -Format "yyyy-MM-dd HH:mm:ss")
# Environment: $Environment

"@

foreach ($key in $urls.Keys | Sort-Object) {
    $url = $urls[$key]
    $varName = $key -replace "photogenius-", "" -replace "-$Environment", ""
    $varName = $varName.ToUpper() -replace "-", "_"
    
    Write-Host "$key"
    Write-Host "  $url"
    Write-Host ""
    
    $envContent += "${varName}_URL=$url`n"
}

# Save to .env file
$envFile = "lambda_urls.env"
$envContent | Out-File -FilePath $envFile -Encoding utf8
Write-Host "URLs saved to: $envFile" -ForegroundColor Green
Write-Host ""

# Create Next.js env file format
$nextEnvContent = @"
# Lambda Function URLs - Add to apps/web/.env.local
# Generated: $(Get-Date -Format "yyyy-MM-dd HH:mm:ss")

"@

$nextEnvContent += "NEXT_PUBLIC_API_ORCHESTRATOR_URL=$($urls["photogenius-orchestrator-$Environment"])`n"
$nextEnvContent += "NEXT_PUBLIC_API_GENERATION_URL=$($urls["photogenius-generation-$Environment"])`n"
$nextEnvContent += "NEXT_PUBLIC_API_SAFETY_URL=$($urls["photogenius-safety-$Environment"])`n"
$nextEnvContent += "NEXT_PUBLIC_API_PROMPT_ENHANCER_URL=$($urls["photogenius-prompt-enhancer-$Environment"])`n"

$nextEnvFile = "nextjs_env.txt"
$nextEnvContent | Out-File -FilePath $nextEnvFile -Encoding utf8
Write-Host "Next.js env vars saved to: $nextEnvFile" -ForegroundColor Green
