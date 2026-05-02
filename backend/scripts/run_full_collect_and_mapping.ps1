# Полный сбор дерева Encar + генерация encar_mapping.json (CSV в data/, JSON в data/).
# Запуск из любой директории:  powershell -File backend/scripts/run_full_collect_and_mapping.ps1
$ErrorActionPreference = "Stop"
$here = $PSScriptRoot
$repoRoot = (Get-Item $here).Parent.Parent.FullName
Set-Location $repoRoot

$pyEncar = Join-Path $repoRoot "backend/scripts/encar_fetch_tree.py"
$pyMap = Join-Path $repoRoot "backend/scripts/build_encar_mapping.py"

Write-Host "=== 1/2 encar_fetch_tree.py (full) ===" -ForegroundColor Cyan
& python $pyEncar
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "`n=== 2/2 build_encar_mapping.py ===" -ForegroundColor Cyan
& python $pyMap
exit $LASTEXITCODE
