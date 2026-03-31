# List SageMaker endpoints in the current region (us-east-1 by default)
# Usage: .\list-sagemaker-endpoints.ps1 [-Region us-east-1]
param([string]$Region = "us-east-1")
aws sagemaker list-endpoints --region $Region --query "Endpoints[*].[EndpointName,EndpointStatus,CreationTime]" --output table
