# PhotoGenius AI - Fix Lambda Code Deployment
# This script directly updates Lambda function code (bypassing SAM issues)

param(
    [string]$Environment = "dev",
    [switch]$DryRun = $false
)

$ErrorActionPreference = "Stop"

Write-Host "🚀 PhotoGenius Lambda Code Update Script" -ForegroundColor Cyan
Write-Host "Environment: $Environment" -ForegroundColor Yellow
Write-Host "Dry Run: $DryRun" -ForegroundColor Yellow
Write-Host ""

# Lambda functions configuration
$lambdaFunctions = @(
    @{
        Name = "photogenius-orchestrator-$Environment"
        CodeDir = "lambda/orchestrator"
        Handler = "handler.lambda_handler"
        Description = "Main orchestrator for quality tier routing"
    },
    @{
        Name = "photogenius-orchestrator-v2-$Environment"
        CodeDir = "lambda/orchestrator_v2"
        Handler = "handler.lambda_handler"
        Description = "Orchestrator v2 with smart routing"
    },
    @{
        Name = "photogenius-prompt-enhancer-$Environment"
        CodeDir = "lambda/prompt_enhancer"
        Handler = "handler.lambda_handler"
        Description = "Rule-based prompt enhancement"
    },
    @{
        Name = "photogenius-generation-$Environment"
        CodeDir = "lambda/generation"
        Handler = "handler.lambda_handler"
        Description = "Direct SageMaker generation"
    },
    @{
        Name = "photogenius-post-processor-$Environment"
        CodeDir = "lambda/post_processor"
        Handler = "handler.lambda_handler"
        Description = "Post-processing and upscaling"
    },
    @{
        Name = "photogenius-safety-$Environment"
        CodeDir = "lambda/safety"
        Handler = "handler.lambda_handler"
        Description = "Safety checks (NSFW, etc.)"
    },
    @{
        Name = "photogenius-training-$Environment"
        CodeDir = "lambda/training"
        Handler = "handler.lambda_handler"
        Description = "LoRA training trigger"
    },
    @{
        Name = "photogenius-refinement-$Environment"
        CodeDir = "lambda/refinement"
        Handler = "handler.lambda_handler"
        Description = "Image refinement and editing"
    }
)

# Check AWS CLI is available
try {
    $awsVersion = aws --version
    Write-Host "✅ AWS CLI installed: $awsVersion" -ForegroundColor Green
} catch {
    Write-Host "❌ AWS CLI not found. Please install it first:" -ForegroundColor Red
    Write-Host "   Download: https://aws.amazon.com/cli/" -ForegroundColor Yellow
    exit 1
}

# Check AWS credentials
try {
    $identity = aws sts get-caller-identity --output json | ConvertFrom-Json
    Write-Host "✅ AWS Credentials valid" -ForegroundColor Green
    Write-Host "   Account: $($identity.Account)" -ForegroundColor Gray
    Write-Host "   User: $($identity.Arn)" -ForegroundColor Gray
    Write-Host ""
} catch {
    Write-Host "❌ AWS credentials not configured" -ForegroundColor Red
    Write-Host "   Run: aws configure" -ForegroundColor Yellow
    exit 1
}

# Create temporary directory for zips
$tempDir = Join-Path $PSScriptRoot "temp_lambda_packages"
if (Test-Path $tempDir) {
    Remove-Item $tempDir -Recurse -Force
}
New-Item -ItemType Directory -Path $tempDir | Out-Null

Write-Host "📦 Packaging and updating Lambda functions..." -ForegroundColor Cyan
Write-Host ""

$successCount = 0
$failCount = 0
$results = @()

foreach ($func in $lambdaFunctions) {
    $functionName = $func.Name
    $codeDir = Join-Path $PSScriptRoot $func.CodeDir
    $zipPath = Join-Path $tempDir "$($func.Name).zip"

    Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor DarkGray
    Write-Host "📦 Processing: $functionName" -ForegroundColor Yellow

    # Check if code directory exists
    if (-not (Test-Path $codeDir)) {
        Write-Host "   ⚠️  Code directory not found: $codeDir" -ForegroundColor Red
        $failCount++
        $results += @{
            Function = $functionName
            Status = "SKIPPED"
            Reason = "Code directory not found"
        }
        continue
    }

    # Check if Lambda function exists
    try {
        $funcInfo = aws lambda get-function --function-name $functionName 2>&1
        if ($LASTEXITCODE -ne 0) {
            Write-Host "   ⚠️  Function does not exist in AWS" -ForegroundColor Red
            $failCount++
            $results += @{
                Function = $functionName
                Status = "SKIPPED"
                Reason = "Function does not exist"
            }
            continue
        }
    } catch {
        Write-Host "   ⚠️  Function does not exist: $functionName" -ForegroundColor Red
        $failCount++
        continue
    }

    Write-Host "   📁 Code directory: $codeDir" -ForegroundColor Gray

    # Package Lambda function
    Write-Host "   📦 Creating deployment package..." -ForegroundColor Cyan

    Push-Location $codeDir
    try {
        # Create zip file with all Python files
        if (Get-Command 7z -ErrorAction SilentlyContinue) {
            # Use 7-Zip if available (faster)
            7z a -tzip $zipPath * -r -mx=9 | Out-Null
        } else {
            # Use PowerShell's Compress-Archive
            Compress-Archive -Path "$codeDir\*" -DestinationPath $zipPath -Force
        }

        $zipSize = (Get-Item $zipPath).Length / 1KB
        Write-Host "   ✅ Package created: $([math]::Round($zipSize, 2)) KB" -ForegroundColor Green
    } catch {
        Write-Host "   ❌ Failed to create package: $_" -ForegroundColor Red
        Pop-Location
        $failCount++
        $results += @{
            Function = $functionName
            Status = "FAILED"
            Reason = "Package creation failed"
        }
        continue
    }
    Pop-Location

    # Update Lambda function code
    if (-not $DryRun) {
        Write-Host "   🚀 Updating Lambda function code..." -ForegroundColor Cyan

        try {
            $updateResult = aws lambda update-function-code `
                --function-name $functionName `
                --zip-file "fileb://$zipPath" `
                --output json 2>&1

            if ($LASTEXITCODE -eq 0) {
                $updateData = $updateResult | ConvertFrom-Json
                Write-Host "   ✅ Code updated successfully!" -ForegroundColor Green
                Write-Host "      Version: $($updateData.Version)" -ForegroundColor Gray
                Write-Host "      Code Size: $([math]::Round($updateData.CodeSize / 1KB, 2)) KB" -ForegroundColor Gray
                Write-Host "      Last Modified: $($updateData.LastModified)" -ForegroundColor Gray

                $successCount++
                $results += @{
                    Function = $functionName
                    Status = "SUCCESS"
                    Version = $updateData.Version
                    CodeSize = $updateData.CodeSize
                }
            } else {
                Write-Host "   ❌ Update failed: $updateResult" -ForegroundColor Red
                $failCount++
                $results += @{
                    Function = $functionName
                    Status = "FAILED"
                    Reason = $updateResult
                }
            }
        } catch {
            Write-Host "   ❌ Update failed: $_" -ForegroundColor Red
            $failCount++
            $results += @{
                Function = $functionName
                Status = "FAILED"
                Reason = $_.Exception.Message
            }
        }
    } else {
        Write-Host "   ⏭️  DRY RUN: Would update $functionName" -ForegroundColor Yellow
        $results += @{
            Function = $functionName
            Status = "DRY_RUN"
        }
    }

    Write-Host ""
}

# Cleanup
Write-Host "🧹 Cleaning up temporary files..." -ForegroundColor Cyan
Remove-Item $tempDir -Recurse -Force

# Summary
Write-Host ""
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor DarkGray
Write-Host "📊 DEPLOYMENT SUMMARY" -ForegroundColor Cyan
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor DarkGray
Write-Host ""

if (-not $DryRun) {
    Write-Host "✅ Success: $successCount" -ForegroundColor Green
    Write-Host "❌ Failed: $failCount" -ForegroundColor $(if ($failCount -gt 0) { "Red" } else { "Gray" })
    Write-Host "📦 Total: $($lambdaFunctions.Count)" -ForegroundColor Cyan
} else {
    Write-Host "⏭️  DRY RUN - No changes made" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "Results:" -ForegroundColor Cyan
foreach ($result in $results) {
    $status = $result.Status
    $color = switch ($status) {
        "SUCCESS" { "Green" }
        "FAILED" { "Red" }
        "SKIPPED" { "Yellow" }
        "DRY_RUN" { "Cyan" }
        default { "Gray" }
    }

    Write-Host "  $($result.Function): " -NoNewline -ForegroundColor Gray
    Write-Host $status -ForegroundColor $color

    if ($result.Reason) {
        Write-Host "    Reason: $($result.Reason)" -ForegroundColor Gray
    }
}

Write-Host ""
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor DarkGray

if ($successCount -gt 0 -and -not $DryRun) {
    Write-Host ""
    Write-Host "✨ Lambda functions updated successfully!" -ForegroundColor Green
    Write-Host ""
    Write-Host "Next steps:" -ForegroundColor Cyan
    Write-Host "1. Test the orchestrator endpoint:" -ForegroundColor Yellow
    Write-Host "   aws lambda invoke --function-name photogenius-orchestrator-$Environment --payload file://test_payload.json response.json" -ForegroundColor Gray
    Write-Host ""
    Write-Host "2. Check CloudWatch Logs:" -ForegroundColor Yellow
    Write-Host "   aws logs tail /aws/lambda/photogenius-orchestrator-$Environment --follow" -ForegroundColor Gray
    Write-Host ""
    Write-Host "3. View API Gateway endpoints:" -ForegroundColor Yellow
    Write-Host "   aws cloudformation describe-stacks --stack-name photogenius-$Environment --query 'Stacks[0].Outputs'" -ForegroundColor Gray
} elseif ($DryRun) {
    Write-Host ""
    Write-Host "💡 Run without -DryRun to actually update the functions" -ForegroundColor Yellow
} else {
    Write-Host ""
    Write-Host "⚠️  Some updates failed. Check the errors above." -ForegroundColor Red
    exit 1
}
