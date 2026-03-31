# PowerShell version of verify-env.sh for Windows

Write-Host "🔍 Verifying environment configuration..." -ForegroundColor Cyan

$errors = 0
$warnings = 0

# Check if .env files exist
if (-not (Test-Path "apps/web/.env.local")) {
    Write-Host "❌ apps/web/.env.local not found" -ForegroundColor Red
    Write-Host "   Create apps/web/.env.local (see docs/ENVIRONMENT_SETUP.md)" -ForegroundColor Yellow
    $errors++
}

if (-not (Test-Path "apps/api/.env.local") -and -not (Test-Path "apps/api/.env")) {
    Write-Host "❌ apps/api/.env.local or apps/api/.env not found" -ForegroundColor Red
    Write-Host "   Create apps/api/.env.local (see docs/ENVIRONMENT_SETUP.md)" -ForegroundColor Yellow
    $errors++
} elseif (Test-Path "apps/api/.env.local") {
    Write-Host "✓ apps/api/.env.local found" -ForegroundColor Green
} elseif (Test-Path "apps/api/.env") {
    Write-Host "⚠️  apps/api/.env found (consider using .env.local)" -ForegroundColor Yellow
    $warnings++
}

# Check Node.js
if (-not (Get-Command node -ErrorAction SilentlyContinue)) {
    Write-Host "❌ Node.js not installed" -ForegroundColor Red
    $errors++
} else {
    $nodeVersion = (node -v).Substring(1)
    $majorVersion = [int]$nodeVersion.Split('.')[0]
    if ($majorVersion -lt 18) {
        Write-Host "⚠️  Node.js version should be 18+" -ForegroundColor Yellow
        $warnings++
    } else {
        Write-Host "✓ Node.js $(node -v)" -ForegroundColor Green
    }
}

# Check Python
if (-not (Get-Command python3.11 -ErrorAction SilentlyContinue)) {
    if (-not (Get-Command py -ErrorAction SilentlyContinue)) {
        Write-Host "❌ Python 3.11 not installed" -ForegroundColor Red
        $errors++
    } else {
        Write-Host "✓ Python (via py launcher)" -ForegroundColor Green
    }
} else {
    Write-Host "✓ Python 3.11" -ForegroundColor Green
}

# Check pnpm
if (-not (Get-Command pnpm -ErrorAction SilentlyContinue)) {
    Write-Host "⚠️  pnpm not installed" -ForegroundColor Yellow
    Write-Host "   Install: npm install -g pnpm" -ForegroundColor Yellow
    $warnings++
} else {
    Write-Host "✓ pnpm $(pnpm -v)" -ForegroundColor Green
}

# Check PostgreSQL
if (-not (Get-Command psql -ErrorAction SilentlyContinue)) {
    Write-Host "⚠️  PostgreSQL client not found" -ForegroundColor Yellow
    $warnings++
} else {
    Write-Host "✓ PostgreSQL client" -ForegroundColor Green
}

# Check Redis (optional)
if (-not (Get-Command redis-cli -ErrorAction SilentlyContinue)) {
    Write-Host "⚠️  Redis client not found (optional)" -ForegroundColor Yellow
    $warnings++
} else {
    Write-Host "✓ Redis client" -ForegroundColor Green
}

# Validate critical env vars if files exist
if (Test-Path "apps/web/.env.local") {
    $webEnv = Get-Content "apps/web/.env.local" | Where-Object { $_ -match '^[^#]' -and $_ -match '=' }
    $webEnvHash = @{}
    $webEnv | ForEach-Object {
        $parts = $_ -split '=', 2
        if ($parts.Length -eq 2) {
            $key = $parts[0].Trim()
            $value = $parts[1].Trim()
            $webEnvHash[$key] = $value
        }
    }
    
    if (-not $webEnvHash["NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY"]) {
        Write-Host "⚠️  NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY not set" -ForegroundColor Yellow
        $warnings++
    }
    if (-not $webEnvHash["CLERK_SECRET_KEY"]) {
        Write-Host "⚠️  CLERK_SECRET_KEY not set" -ForegroundColor Yellow
        $warnings++
    }
}

if (Test-Path "apps/api/.env.local") {
    $apiEnv = Get-Content "apps/api/.env.local" | Where-Object { $_ -match '^[^#]' -and $_ -match '=' }
    $apiEnvHash = @{}
    $apiEnv | ForEach-Object {
        $parts = $_ -split '=', 2
        if ($parts.Length -eq 2) {
            $key = $parts[0].Trim()
            $value = $parts[1].Trim()
            $apiEnvHash[$key] = $value
        }
    }
    
    if (-not $apiEnvHash["DATABASE_URL"]) {
        Write-Host "⚠️  DATABASE_URL not set" -ForegroundColor Yellow
        $warnings++
    }
    if (-not $apiEnvHash["CLERK_SECRET_KEY"]) {
        Write-Host "⚠️  CLERK_SECRET_KEY not set" -ForegroundColor Yellow
        $warnings++
    }
}

# Summary
Write-Host ""
Write-Host "═══════════════════════════════════════" -ForegroundColor Cyan
if ($errors -eq 0 -and $warnings -eq 0) {
    Write-Host "✅ All checks passed!" -ForegroundColor Green
    exit 0
} elseif ($errors -eq 0) {
    Write-Host "⚠️  $warnings warning(s) found" -ForegroundColor Yellow
    exit 0
} else {
    Write-Host "❌ $errors error(s), $warnings warning(s)" -ForegroundColor Red
    exit 1
}
