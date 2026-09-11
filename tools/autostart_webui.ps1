# Logon wrapper for the FareAlertWebUI scheduled task: no-op when the
# webui is already listening (manual start / another copy), else launch hidden.
param([string]$RepoDir = (Split-Path $PSScriptRoot -Parent))
$Port = 8765
try {
  $cfg = Get-Content (Join-Path $RepoDir "config.json") -Raw -Encoding UTF8 | ConvertFrom-Json
  if ($cfg.webui -and $cfg.webui.port) { $Port = [int]$cfg.webui.port }
} catch { }
$c = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
if ($c) {
  Write-Output "SKIP: port $Port already listening"
  exit 0
}
Start-Process -WindowStyle Hidden -FilePath python `
  -ArgumentList "-X", "utf8", "webui.py" -WorkingDirectory $RepoDir
Write-Output "STARTED webui (hidden) -> http://127.0.0.1:$Port"
