param([string]$RepoDir = (Split-Path $PSScriptRoot -Parent))
$ErrorActionPreference = "Stop"
$c = Get-NetTCPConnection -LocalPort 8765 -State Listen -ErrorAction SilentlyContinue
if ($c) {
  $pid8765 = $c[0].OwningProcess
  $proc = Get-CimInstance Win32_Process -Filter "ProcessId = $pid8765"
  if ($proc -and $proc.CommandLine -match "webui\.py") {
    Stop-Process -Id $pid8765 -Force
    Start-Sleep -Milliseconds 600
  } else {
    Write-Output ("SKIP kill: port 8765 held by pid " + $pid8765 + " (not webui.py)")
  }
}
Start-Process -WindowStyle Hidden -FilePath python -ArgumentList "-X", "utf8", "webui.py" -WorkingDirectory $RepoDir
Start-Sleep -Seconds 3
try {
  Invoke-RestMethod "http://127.0.0.1:8765/api/sched-stats" -TimeoutSec 10 | ConvertTo-Json -Compress
} catch {
  Write-Output ("FAIL: " + $_.Exception.Message)
}
