# v0.51: force-restart the FareAlert worker loop (kill every running
# "main.py --loop", then relaunch hidden). Unlike autostart_worker.ps1
# (a no-op when a loop exists), this guarantees the freshly deployed
# code actually runs - closing the stale-worker root cause where a
# pre-update process kept re-writing snapshot.json for hours.
param([string]$RepoDir = (Split-Path $PSScriptRoot -Parent))
$old = Get-CimInstance Win32_Process -Filter "Name LIKE 'python%'" `
  -ErrorAction SilentlyContinue | Where-Object {
    $_.CommandLine -match 'main\.py' -and $_.CommandLine -match '--loop' }
foreach ($p in @($old)) {
  if ($p.ProcessId) {
    Stop-Process -Id $p.ProcessId -Force -ErrorAction SilentlyContinue
  }
}
if (@($old).Count -gt 0) { Start-Sleep -Milliseconds 800 }
Start-Process -WindowStyle Hidden -FilePath python `
  -ArgumentList "-X", "utf8", "main.py", "--loop" -WorkingDirectory $RepoDir
Write-Output ("RESTARTED fare-alert worker loop (killed " + @($old).Count + ", relaunched hidden)")
