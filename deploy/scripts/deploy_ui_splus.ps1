# Deploy UI S+ to 62.76.31.51 — password via env or prompt (not stored in repo).
param(
  [string]$Password = $env:WRA_DEPLOY_PASSWORD
)

if (-not $Password) {
  $sec = Read-Host "Deploy password (root@62.76.31.51)" -AsSecureString
  $ptr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($sec)
  try { $Password = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($ptr) }
  finally { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($ptr) }
}

Set-Location (Split-Path (Split-Path $PSScriptRoot))
python deploy/scripts/_remote_git_pull_deploy.py $Password
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
Write-Host "Deploy finished OK"
