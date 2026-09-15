# Register the every-15-min FareAlertWatchdog scheduled task
# (self-heal layer 4: watches the webui itself at runtime; best-effort
# - the other three layers keep working when registration is denied).
# Usage:
#   powershell -NoProfile -ExecutionPolicy Bypass -File tools/register_watchdog_task.ps1
$ErrorActionPreference = 'Stop'
$repo = Split-Path $PSScriptRoot -Parent
$script = Join-Path $repo 'tools/watchdog.py'
try {
  $existing = Get-ScheduledTask -TaskName 'FareAlertWatchdog' -ErrorAction SilentlyContinue
  if ($existing) { Unregister-ScheduledTask -TaskName 'FareAlertWatchdog' -Confirm:$false }
  $action = New-ScheduledTaskAction -Execute 'python.exe' -Argument ('-X utf8 "' + $script + '"')
  $trigger = New-ScheduledTaskTrigger -Once -At (Get-Date) -RepetitionInterval (New-TimeSpan -Minutes 15) -RepetitionDuration (New-TimeSpan -Days 3650)
  Register-ScheduledTask -TaskName 'FareAlertWatchdog' -Action $action -Trigger $trigger | Out-Null
  Write-Output 'TASK REGISTERED'
} catch {
  Write-Output ('DENIED: ' + $_.Exception.Message)
}
