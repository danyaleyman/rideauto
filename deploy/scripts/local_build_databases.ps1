#Requires -Version 5.1
<#
.SYNOPSIS
  Локальный scrape Korea (Encar) + China (Che168) → PostgreSQL (Docker :5433) → D:\Database

.USAGE
  # 1) Запустите Docker Desktop
  # 2) Добавьте прокси Encar в scraper_config.local.yaml (proxy.urls) для полного каталога
  # 3) Для Che168 опционально proxy + playwright (che168_scraper.local.yaml)
  .\deploy\scripts\local_build_databases.ps1 -Smoke          # проверка (~10+20 машин)
  .\deploy\scripts\local_build_databases.ps1 -Full           # полный scrape (дни, нужен прокси Encar)
  .\deploy\scripts\local_build_databases.ps1 -ExportOnly   # только выгрузить текущую БД
#>
param(
  [switch]$Smoke,
  [switch]$Full,
  [switch]$ExportOnly,
  [string]$ExportDir = "D:\Database"
)

$ErrorActionPreference = "Stop"
$Repo = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$VenvPy = Join-Path $Repo ".venv\Scripts\python.exe"
$PgDump = "docker compose exec -T postgres pg_dump -U wra -d wra -Fc --no-owner --no-acl"
$Stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$OutDir = Join-Path $ExportDir "rideauto-local-$Stamp"

function Ensure-Venv {
  if (-not (Test-Path $VenvPy)) {
    Write-Host "Creating Python 3.11 venv…" -ForegroundColor Cyan
    Push-Location $Repo
    py -3.11 -m venv .venv
    & $VenvPy -m pip install -q -r backend\requirements.txt
    Pop-Location
  }
}

function Ensure-Postgres {
  Push-Location $Repo
  if (-not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
    Add-Content ".env" "`nPOSTGRES_PORT=5433`nDATABASE_URL=postgresql://wra:wra@127.0.0.1:5433/wra"
  }
  docker compose up -d postgres
  $deadline = (Get-Date).AddMinutes(2)
  do {
    $ok = docker compose exec -T postgres pg_isready -U wra -d wra 2>$null
    if ($LASTEXITCODE -eq 0) { break }
    Start-Sleep -Seconds 2
  } while ((Get-Date) -lt $deadline)
  if ($LASTEXITCODE -ne 0) { throw "Postgres not ready on port 5433" }
  & $VenvPy deploy\scripts\_local_pg_init.py
  if ($LASTEXITCODE -ne 0) { throw "Schema init failed" }
  Pop-Location
}

function Run-Encar {
  param([int]$MaxCars = 0)
  Push-Location (Join-Path $Repo "backend")
  $env:PYTHONPATH = "."
  $env:DATABASE_URL = "postgresql://wra:wra@127.0.0.1:5433/wra"
  $env:SKIP_POSTGRES_CATALOG_SYNC = "1"
  $env:SKIP_FRONTEND_EXPORT = "1"
  $cfg = if ($MaxCars -gt 0 -and $MaxCars -le 50) { "..\scraper_config.smoke.yaml" } else { "..\scraper_config.yaml" }
  Write-Host "=== Encar scrape (max-cars=$MaxCars) ===" -ForegroundColor Cyan
  if ($MaxCars -gt 0) {
    & $VenvPy encar_scraper.py --config $cfg --max-cars $MaxCars
  } else {
    & $VenvPy encar_scraper.py --config $cfg
  }
  if ($LASTEXITCODE -ne 0) { throw "encar_scraper failed" }
  Pop-Location
}

function Run-Che168 {
  param([int]$MaxCars = 0)
  Push-Location (Join-Path $Repo "backend")
  $env:PYTHONPATH = "."
  $env:DATABASE_URL = "postgresql://wra:wra@127.0.0.1:5433/wra"
  $env:SKIP_POSTGRES_CATALOG_SYNC = "1"
  Write-Host "=== Che168 scrape (max-cars=$MaxCars, playwright bootstrap) ===" -ForegroundColor Cyan
  & $VenvPy -m pip install -q playwright 2>$null
  & $VenvPy -m playwright install chromium 2>$null
  if ($MaxCars -gt 0) {
    & $VenvPy che168_scraper.py --config ..\che168_scraper.yaml --max-cars $MaxCars
  } else {
    & $VenvPy che168_scraper.py --config ..\che168_scraper.yaml
  }
  if ($LASTEXITCODE -ne 0) { throw "che168_scraper failed" }
  Pop-Location
}

function Export-Database {
  Push-Location $Repo
  New-Item -ItemType Directory -Force -Path $OutDir | Out-Null
  Write-Host "Export → $OutDir" -ForegroundColor Cyan

  docker compose exec -T postgres pg_dump -U wra -d wra --schema-only --no-owner --no-acl |
    Set-Content -Encoding utf8 (Join-Path $OutDir "schema.sql")

  $fullDump = Join-Path $OutDir "wra_full.custom.dump"
  cmd /c "docker compose exec -T postgres pg_dump -U wra -d wra -Fc -Z6 --no-owner --no-acl > `"$fullDump`""

  docker compose exec -T postgres psql -U wra -d wra -v ON_ERROR_STOP=1 -c @"
DROP SCHEMA IF EXISTS wra_export CASCADE;
CREATE SCHEMA wra_export;
CREATE TABLE wra_export.korea_cars AS SELECT * FROM public.cars WHERE source = 'encar';
CREATE TABLE wra_export.china_cars AS SELECT * FROM public.cars WHERE source = 'che168';
CREATE TABLE wra_export.korea_car_images AS
  SELECT ci.* FROM public.car_images ci JOIN public.cars c ON c.id = ci.car_pk WHERE c.source = 'encar';
CREATE TABLE wra_export.china_car_images AS
  SELECT ci.* FROM public.car_images ci JOIN public.cars c ON c.id = ci.car_pk WHERE c.source = 'che168';
"@

  $regDump = Join-Path $OutDir "regional_split.custom.dump"
  cmd /c "docker compose exec -T postgres pg_dump -U wra -d wra -Fc -Z6 --no-owner --no-acl -n wra_export > `"$regDump`""

  docker compose exec -T postgres psql -U wra -d wra -c "DROP SCHEMA IF EXISTS wra_export CASCADE;" | Out-Null

  docker compose exec -T postgres psql -U wra -d wra -Atc "SELECT source || E'\t' || COUNT(*)::text FROM cars GROUP BY source ORDER BY source;" |
    Set-Content (Join-Path $OutDir "counts.txt")

  @"
# Rideauto local backup ($Stamp)

- schema.sql — схема
- wra_full.custom.dump — полная БД (Korea+China)
- regional_split.custom.dump — схема wra_export: korea_cars, china_cars, *_car_images
- counts.txt — число строк по source

Restore full:
  docker compose exec -T postgres pg_restore -U wra -d wra --no-owner --clean < wra_full.custom.dump

DSN: postgresql://wra:wra@127.0.0.1:5433/wra
"@ | Set-Content (Join-Path $OutDir "README-RESTORE.md") -Encoding utf8

  Pop-Location
  Write-Host "Done: $OutDir" -ForegroundColor Green
}

Ensure-Venv
Ensure-Postgres

if ($ExportOnly) {
  Export-Database
  exit 0
}

if ($Smoke) {
  Run-Encar -MaxCars 10
  Run-Che168 -MaxCars 20
  Export-Database
  exit 0
}

if ($Full) {
  Run-Encar -MaxCars 0
  Run-Che168 -MaxCars 0
  Export-Database
  exit 0
}

Write-Host @"

Usage:
  .\deploy\scripts\local_build_databases.ps1 -Smoke
  .\deploy\scripts\local_build_databases.ps1 -Full
  .\deploy\scripts\local_build_databases.ps1 -ExportOnly

Перед -Full добавьте proxy Encar в scraper_config.local.yaml (см. scraper_config.local.example.yaml).

"@ -ForegroundColor Yellow
