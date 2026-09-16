# Register the every-15-min FareAlertWatchdog scheduled task
# (self-heal layer 4: watches the webui itself at runtime; best-effort
# - the other three layers keep working when registration is denied).
# Usage:
#   powershell -NoProfile -ExecutionPolicy Bypass -File tools/register_watchdog_task.ps1
$ErrorActionPreference = 'Stop'
$repo = Split-Path $PSScriptRoot -Parent
$script = Join-Path $repo 'tools/watchdog.py'
# v1.00: resolve the ABSOLUTE interpreter path at registration time.
# The old bare 'python.exe' resolved differently inside the task
# session (WindowsApps alias stub -> 0x80070002 at every 15-min
# fire while interactive runs worked fine). sys.executable is the
# real interpreter behind the alias and resolves everywhere.
$py = 'python.exe'
try {
  $probe = & python -c 'import sys; print(sys.executable)' 2>$null
  if ($probe) { $py = ($probe | Select-Object -First 1).Trim() }
} catch { $py = 'python.exe' }
if (-not (Test-Path $py)) {
  Write-Output ('DENIED: interpreter not found: ' + $py)
  exit 1
}
try {
  $existing = Get-ScheduledTask -TaskName 'FareAlertWatchdog' -ErrorAction SilentlyContinue
  if ($existing) { Unregister-ScheduledTask -TaskName 'FareAlertWatchdog' -Confirm:$false }
  $action = New-ScheduledTaskAction -Execute $py -Argument ('-X utf8 "' + $script + '"')
  $trigger = New-ScheduledTaskTrigger -Once -At (Get-Date) -RepetitionInterval (New-TimeSpan -Minutes 15) -RepetitionDuration (New-TimeSpan -Days 3650)
  Register-ScheduledTask -TaskName 'FareAlertWatchdog' -Action $action -Trigger $trigger | Out-Null
  Write-Output ('TASK REGISTERED via ' + $py)
} catch {
  Write-Output ('DENIED: ' + $_.Exception.Message)
}
