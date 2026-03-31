# PhotoGenius AI - setup verification (Windows PowerShell).
# Checks: Node version, pnpm, Python, dependencies installed.
# Usage: .\scripts\verify-setup.ps1
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot\..
$Fail = 0

Write-Host ">>> PhotoGenius AI - verify setup"
Write-Host ""

Write-Host "1. Node (required >=18)"
if (Get-Command node -ErrorAction SilentlyContinue) {
    $v = (node -v)
    Write-Host "    $v"
    $major = [int]($v -replace 'v(\d+)\..*', '$1')
    if ($major -lt 18) { Write-Host "    [WARN] Use Node 18+"; $Fail = 1 }
}
else { Write-Host "  [X] node not found"; $Fail = 1 }
Write-Host ""

Write-Host "2. pnpm (required >=8)"
if (Get-Command pnpm -ErrorAction SilentlyContinue) { pnpm -v } else { Write-Host "  [X] pnpm not found"; $Fail = 1 }
Write-Host ""

Write-Host "3. Python (required 3.11+)"
if ((Get-Command py -ErrorAction SilentlyContinue) -or (Get-Command python -ErrorAction SilentlyContinue)) {
    if (Get-Command py -ErrorAction SilentlyContinue) { py -3.11 --version 2>$null } else { python --version }
}
else { Write-Host "  [X] Python not found"; $Fail = 1 }
Write-Host ""

Write-Host "4. Dependencies (pnpm install)"
if (Test-Path node_modules) { Write-Host "  [OK] node_modules" } else { Write-Host "  [X] Run pnpm install"; $Fail = 1 }
Write-Host ""

Write-Host "5. Prisma client"
if (Test-Path node_modules\.prisma) { Write-Host "  [OK] Prisma" } elseif (Test-Path node_modules\@prisma\client) { Write-Host "  [OK] Prisma" } else { Write-Host "  [X] Run pnpm run build in packages/database"; $Fail = 1 }
Write-Host ""

Write-Host "6. .env"
if (Test-Path .env) { Write-Host "  [OK] .env" } else { Write-Host "  [X] Create .env or use apps/*/.env.local"; $Fail = 1 }
Write-Host ""

if ($Fail -eq 1) { Write-Host ">>> Some checks failed."; exit 1 }
Write-Host ">>> All checks passed."
