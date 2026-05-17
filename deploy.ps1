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

ssh rideauto "cd /opt/rideauto && bash deploy/scripts/server_compose_env_fix_and_deploy.sh"
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
