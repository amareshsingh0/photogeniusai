# Full setup: install deps and run all math/diagram renderer tests (no skips).
# Run from ai-pipeline: .\scripts\run_math_diagram_tests.ps1
# Or from repo root: .\ai-pipeline\scripts\run_math_diagram_tests.ps1

$ErrorActionPreference = "Stop"
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$aiPipeline = Resolve-Path (Join-Path $scriptDir "..")
Set-Location $aiPipeline

Write-Host "Installing requirements (sympy, antlr4, matplotlib, Pillow)..." -ForegroundColor Cyan
pip install -r requirements.txt --quiet
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "Running all 15 math/diagram renderer tests (no skips)..." -ForegroundColor Cyan
python -m pytest tests/test_math_diagram_renderer.py -v -p no:asyncio
exit $LASTEXITCODE
