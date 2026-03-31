# Check EC2 model staging status
param(
    [string]$InstanceId = "i-069912a52a53a6e47"
)

Write-Host "=== EC2 Model Staging Status ===" -ForegroundColor Cyan

# Check instance state
$instance = aws ec2 describe-instances --instance-ids $InstanceId --region us-east-1 --query "Reservations[0].Instances[0]" --output json 2>$null | ConvertFrom-Json
Write-Host "Instance: $InstanceId"
Write-Host "State: $($instance.State.Name)"
Write-Host "Launch Time: $($instance.LaunchTime)"

# Check S3 for uploads
Write-Host "`n=== S3 Upload Status ===" -ForegroundColor Yellow
$turboFiles = aws s3 ls s3://photogenius-models-dev/models/sdxl-turbo/ --region us-east-1 --recursive 2>$null
$turboCount = ($turboFiles | Measure-Object -Line).Lines
Write-Host "SDXL Turbo files in S3: $turboCount"

$baseFiles = aws s3 ls s3://photogenius-models-dev/models/stable-diffusion-xl-base-1.0/ --region us-east-1 --recursive 2>$null
$baseCount = ($baseFiles | Measure-Object -Line).Lines
Write-Host "SDXL Base files in S3: $baseCount"

# Run SSM command to check download status
Write-Host "`n=== EC2 Download Status ===" -ForegroundColor Yellow

# Create temp file for parameters
$paramsFile = "$env:TEMP\ssm-params.json"
@{commands = @("du -sh /tmp/sdxl-turbo /tmp/sdxl-base 2>/dev/null; ls /tmp/ | head -5")} | ConvertTo-Json | Out-File $paramsFile -Encoding ascii

$cmdResult = aws ssm send-command --instance-ids $InstanceId --document-name "AWS-RunShellScript" --parameters "file://$paramsFile" --region us-east-1 --output json 2>$null | ConvertFrom-Json

if ($cmdResult.Command.CommandId) {
    Start-Sleep -Seconds 5
    $output = aws ssm get-command-invocation --command-id $cmdResult.Command.CommandId --instance-id $InstanceId --region us-east-1 --query "StandardOutputContent" --output text 2>$null
    # Filter out non-ASCII chars
    $cleanOutput = $output -replace '[^\x20-\x7E\r\n]', ''
    Write-Host $cleanOutput
}
