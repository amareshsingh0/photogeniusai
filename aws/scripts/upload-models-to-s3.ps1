# Upload SDXL models to S3 for SageMaker
# Run this ONCE to pre-stage models so SageMaker can load them quickly
param(
    [string]$Region = "us-east-1",
    [string]$BucketName = "photogenius-models-dev"
)

Write-Host "=== PhotoGenius Model Uploader ===" -ForegroundColor Cyan
Write-Host "This will download SDXL models and upload to S3." -ForegroundColor Yellow
Write-Host "Estimated download: ~14GB (Base + Turbo)" -ForegroundColor Yellow
Write-Host ""

# Check if bucket exists
$exists = aws s3api head-bucket --bucket $BucketName --region $Region 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "Creating bucket $BucketName..." -ForegroundColor Yellow
    aws s3api create-bucket --bucket $BucketName --region $Region
}

# Create temp directory
$tempDir = "$env:TEMP\photogenius-models"
if (-not (Test-Path $tempDir)) {
    New-Item -ItemType Directory -Path $tempDir | Out-Null
}

Write-Host "`nStep 1: Installing huggingface_hub..." -ForegroundColor Cyan
pip install huggingface_hub --quiet

Write-Host "`nStep 2: Downloading models (this will take a while)..." -ForegroundColor Cyan

# Download SDXL Turbo (smaller, faster)
Write-Host "  Downloading SDXL Turbo (~3GB)..." -ForegroundColor Gray
$turboDir = "$tempDir\sdxl-turbo" -replace '\\', '/'
python -c "from huggingface_hub import snapshot_download; snapshot_download(repo_id='stabilityai/sdxl-turbo', local_dir=r'$turboDir', local_dir_use_symlinks=False, ignore_patterns=['*.md', '*.txt', 'samples/*']); print('SDXL Turbo downloaded')"

# Download SDXL Base
Write-Host "  Downloading SDXL Base (~7GB)..." -ForegroundColor Gray  
$baseDir = "$tempDir\stable-diffusion-xl-base-1.0" -replace '\\', '/'
python -c "from huggingface_hub import snapshot_download; snapshot_download(repo_id='stabilityai/stable-diffusion-xl-base-1.0', local_dir=r'$baseDir', local_dir_use_symlinks=False, ignore_patterns=['*.md', '*.txt', 'samples/*']); print('SDXL Base downloaded')"

Write-Host "`nStep 3: Uploading to S3..." -ForegroundColor Cyan
aws s3 sync "$tempDir\sdxl-turbo" "s3://$BucketName/models/sdxl-turbo" --region $Region
aws s3 sync "$tempDir\stable-diffusion-xl-base-1.0" "s3://$BucketName/models/stable-diffusion-xl-base-1.0" --region $Region

Write-Host "`n=== DONE ===" -ForegroundColor Green
Write-Host "Models uploaded to s3://$BucketName/models/" -ForegroundColor Cyan
Write-Host ""
Write-Host "Next step: Update SageMaker inference code to load from S3 instead of HuggingFace"
