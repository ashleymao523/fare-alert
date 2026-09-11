# Logon wrapper for the FareAlert worker loop: no-op when a
# "main.py --loop" process is already running, else launch hidden.
# The loop refreshes prices AND builds board coverage one weekday at a
# time (2 requests/board/day hard cap), so it must survive reboots to
# close the "missing departure times" gap mechanically.
param([string]$RepoDir = (Split-Path $PSScriptRoot -Parent))
$running = Get-CimInstance Win32_Process -Filter "Name LIKE 'python%'" `
  -ErrorAction SilentlyContinue | Where-Object {
    $_.CommandLine -match 'main\.py' -and $_.CommandLine -match '--loop' }
if ($running) {
  $p = ($running | Select-Object -First 1).ProcessId
  Write-Output "SKIP: worker loop already running (pid $p)"
  exit 0
}
Start-Process -WindowStyle Hidden -FilePath python `
  -ArgumentList "-X", "utf8", "main.py", "--loop" -WorkingDirectory $RepoDir
Write-Output "STARTED fare-alert worker loop (hidden)"
