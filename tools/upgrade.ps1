# tools/upgrade.ps1 - v0.74 one-command upgrade for source deployments
# (Windows). Docker deployments upgrade with: docker compose pull && up -d.
param([switch]$NoPull)
$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")
if (-not $NoPull) {
  Write-Output "[1/3] git pull --ff-only ..."
  git pull --ff-only
  if ($LASTEXITCODE -ne 0) { throw "git pull failed - resolve local changes first" }
} else {
  Write-Output "[1/3] skip pull (-NoPull)"
}
Write-Output "[2/3] web build ..."
if (Get-Command node -ErrorAction SilentlyContinue) {
  Push-Location web
  npm install --no-audit --no-fund
  if ($LASTEXITCODE -ne 0) { Pop-Location; throw "npm install failed" }
  npm run build
  if ($LASTEXITCODE -ne 0) { Pop-Location; throw "npm build failed" }
  Pop-Location
} else {
  Write-Warning "node not found - skip web rebuild (use the docker image instead)"
}
Write-Output "[3/3] restart services ..."
& powershell -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot "restart_all.ps1")
