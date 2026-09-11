# Logon wrapper for the FareAlertWebUI scheduled task: no-op when the
# webui is already listening (manual start / another copy), else launch hidden.
param([string]$RepoDir = (Split-Path $PSScriptRoot -Parent))
$c = Get-NetTCPConnection -LocalPort 8765 -State Listen -ErrorAction SilentlyContinue
if ($c) {
  Write-Output "SKIP: port 8765 already listening"
  exit 0
}
Start-Process -WindowStyle Hidden -FilePath python `
  -ArgumentList "-X", "utf8", "webui.py" -WorkingDirectory $RepoDir
Write-Output "STARTED webui (hidden) -> http://127.0.0.1:8765"
