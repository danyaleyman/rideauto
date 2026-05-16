$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

git add .
git commit -m "quick update"
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

git push server main
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
