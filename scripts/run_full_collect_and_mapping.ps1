# Полный сбор дерева Encar + генерация encar_mapping.json
# Использование: .\scripts\run_full_collect_and_mapping.ps1
$ErrorActionPreference = "Stop"
$root = (Get-Item $PSScriptRoot).Parent.FullName
Set-Location $root

Write-Host "=== 1/2 encar_fetch_tree.py (full) ===" -ForegroundColor Cyan
& python scripts/encar_fetch_tree.py
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "`n=== 2/2 build_encar_mapping.py ===" -ForegroundColor Cyan
& python scripts/build_encar_mapping.py
exit $LASTEXITCODE
