# Register the daily 07:30 FareAlertWorkerRevive scheduled task
# (best-effort layer 3 of the self-heal stack; the webui-embedded
# 07:00 supervisor and the logon Startup .cmd keep working even
# when a hardened host denies this registration).
# Usage:
#   powershell -NoProfile -ExecutionPolicy Bypass -File tools/register_revive_task.ps1
$ErrorActionPreference = 'Stop'
$repo = Split-Path $PSScriptRoot -Parent
$wrapper = Join-Path $repo 'tools/autostart_worker.ps1'
try {
  $existing = Get-ScheduledTask -TaskName 'FareAlertWorkerRevive' -ErrorAction SilentlyContinue
  if ($existing) { Unregister-ScheduledTask -TaskName 'FareAlertWorkerRevive' -Confirm:$false }
  $action = New-ScheduledTaskAction -Execute 'powershell.exe' -Argument ('-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "' + $wrapper + '"')
  $trigger = New-ScheduledTaskTrigger -Daily -At 07:30
  Register-ScheduledTask -TaskName 'FareAlertWorkerRevive' -Action $action -Trigger $trigger | Out-Null
  Write-Output 'TASK REGISTERED'
} catch {
  Write-Output ('DENIED: ' + $_.Exception.Message)
}
