# 10 машин + один цикл daily update внутри Docker (Python 3.12, Postgres из compose).
# Из корня репозитория:
#   docker compose up -d postgres
#   .\backend\scripts\run_encar_smoke_docker.ps1

$ErrorActionPreference = "Stop"
$Repo = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
Push-Location $Repo
try {
  docker compose up -d postgres
  if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

  $vol = "${Repo}:/repo:ro"
  $envArgs = @(
    "-e", "PYTHONPATH=/repo/backend",
    "-e", "DATABASE_URL=postgresql://wra:wra@postgres:5432/wra",
    "-e", "SKIP_POSTGRES_CATALOG_SYNC=1",
    "-e", "SKIP_FRONTEND_EXPORT=1"
  )

  Write-Host "=== encar_scraper --max-cars 10 (smoke config) ===" -ForegroundColor Cyan
  docker compose run --rm @envArgs -v $vol -w /repo/backend api python encar_scraper.py --config /repo/scraper_config.smoke.yaml --max-cars 10
  if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

  Write-Host "`n=== encar_daily_update --once (smoke: discover + sold sample + pending) ===" -ForegroundColor Cyan
  docker compose run --rm @envArgs -v $vol -w /repo/backend api python encar_daily_update.py --config /repo/scraper_config.smoke.yaml --once
  if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

  Write-Host "`nГотово." -ForegroundColor Green
} finally {
  Pop-Location
}
