# Recreate API venv (fixes "Unable to create process" when venv was moved/copied)
# Run from: c:\desktop\PhotoGenius AI\apps\api

$apiDir = "c:\desktop\PhotoGenius AI\apps\api"
Set-Location $apiDir

Write-Host "Removing old .venv (from previous project path)..." -ForegroundColor Yellow
if (Test-Path .venv) {
    Remove-Item -Recurse -Force .venv
}

Write-Host "Creating new virtual environment..." -ForegroundColor Cyan
python -m venv .venv
if ($LASTEXITCODE -ne 0) {
    Write-Host "Error: python -m venv failed. Make sure Python is installed and in PATH." -ForegroundColor Red
    exit 1
}

Write-Host "Installing requirements-minimal.txt (this may take a few minutes)..." -ForegroundColor Cyan
.\.venv\Scripts\pip install -r requirements-minimal.txt
if ($LASTEXITCODE -ne 0) {
    Write-Host "Error: pip install failed." -ForegroundColor Red
    exit 1
}

Write-Host "Done. You can now run: npx pnpm run dev" -ForegroundColor Green
