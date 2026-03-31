# Delete a SageMaker endpoint (and optionally its config) after confirming it exists.
# Usage: .\delete-sagemaker-endpoint.ps1 -EndpointName "photogenius-standard" [-Region us-east-1]
param(
    [Parameter(Mandatory = $true)]
    [string]$EndpointName,
    [string]$Region = "us-east-1"
)
$exists = aws sagemaker describe-endpoint --endpoint-name $EndpointName --region $Region 2>$null
if (-not $exists) {
    Write-Host "Endpoint '$EndpointName' not found in $Region. List endpoints: .\list-sagemaker-endpoints.ps1 -Region $Region" -ForegroundColor Yellow
    exit 1
}
Write-Host "Deleting endpoint: $EndpointName (region: $Region) ..."
aws sagemaker delete-endpoint --endpoint-name $EndpointName --region $Region
if ($LASTEXITCODE -eq 0) { Write-Host "Delete requested. Endpoint will transition to Deleting then disappear." -ForegroundColor Green }
