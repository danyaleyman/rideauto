param(
    [Parameter(Mandatory = $true)]
    [string]$m
)

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

git add .
git commit -m $m
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

git push server main
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

ssh rideauto "cd /opt/rideauto && git pull && docker compose build web && docker compose up -d --no-deps web"
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
