# Один цикл encar_daily_update (discover + remove sold + only-pending) в локальную Postgres из docker-compose.
# Предусловие: `docker compose up -d postgres` из корня репо, схема применена (initdb 01-schema.sql).
# Использование из PowerShell:  .\backend\scripts\run_encar_local_daily.ps1

$ErrorActionPreference = "Stop"
$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$Backend = Join-Path $RepoRoot "backend"
$Cfg = Join-Path $RepoRoot "scraper_config.yaml"

if (-not (Test-Path $Cfg)) {
    Write-Error "Не найден $Cfg"
}

if (-not $env:DATABASE_URL) {
    $env:DATABASE_URL = "postgresql://wra:wra@127.0.0.1:5432/wra"
}

# Ускорить итерацию: без тяжёлого postgres_catalog_sync после only-pending (при необходимости снимите)
if (-not $env:SKIP_POSTGRES_CATALOG_SYNC) { $env:SKIP_POSTGRES_CATALOG_SYNC = "1" }
if (-not $env:SKIP_FRONTEND_EXPORT) { $env:SKIP_FRONTEND_EXPORT = "1" }

if (-not (Test-Path (Join-Path $RepoRoot "scraper_config.local.yaml"))) {
    Write-Host "Подсказка: скопируйте scraper_config.local.example.yaml -> scraper_config.local.yaml для DSN и proxy." -ForegroundColor Yellow
}

Push-Location $Backend
try {
    $env:PYTHONPATH = "."
    python encar_daily_update.py --config $Cfg --once
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
} finally {
    Pop-Location
}
