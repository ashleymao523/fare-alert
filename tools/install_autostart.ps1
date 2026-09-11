# Install/uninstall the FareAlert WebUI logon autostart (current user).
# Usage:
#   powershell -NoProfile -ExecutionPolicy Bypass -File tools/install_autostart.ps1
#   powershell ... -File tools/install_autostart.ps1 -Uninstall
param(
  [switch]$Uninstall,
  [ValidateSet("registry", "task")]
  [string]$Mode = "registry",
  [string]$RepoDir = (Split-Path $PSScriptRoot -Parent),
  [string]$TaskName = "FareAlertWebUI",
  [string]$RunKey = "HKCU:\Software\Microsoft\Windows\CurrentVersion\Run",
  [string]$RunName = "FareAlertWebUI"
)
$ErrorActionPreference = "Stop"

if ($Uninstall) {
  $removed = @()
  $t = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
  if ($t) {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
    $removed += "task:$TaskName"
  }
  $rk = Get-Item $RunKey -ErrorAction SilentlyContinue
  if ($rk -and $rk.GetValue($RunName)) {
    Remove-ItemProperty -Path $RunKey -Name $RunName
    $removed += "registry:$RunName"
  }
  if ($removed) { Write-Output ("REMOVED " + ($removed -join ", ")) }
  else { Write-Output "NOOP: no autostart entry found" }
  exit 0
}

# autostart_webui.ps1 self-guards: skips launch when 8765 is listening.
$wrapper = Join-Path $RepoDir "tools\autostart_webui.ps1"
$cmdLine = 'powershell.exe -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "{0}"' -f $wrapper

if ($Mode -eq "registry") {
  # Preferred: per-user HKCU Run key (no admin, no task-scheduler policy)
  if (-not (Test-Path $RunKey)) { New-Item -Path $RunKey -Force | Out-Null }
  Set-ItemProperty -Path $RunKey -Name $RunName -Value $cmdLine
  $ok = (Get-ItemProperty $RunKey).$RunName -eq $cmdLine
  if ($ok) {
    Write-Output ("INSTALLED HKCU Run entry $RunName -> " + $RepoDir)
    Write-Output "Next logon auto-starts http://127.0.0.1:8765 (skips if already listening)."
  } else { Write-Output "FAIL: registry write did not stick"; exit 1 }
} else {
  # Fallback: scheduled task (needs elevation on locked-down hosts)
  $existing = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
  if ($existing) { Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false }
  $action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument $cmdLine
  $trigger = New-ScheduledTaskTrigger -AtLogOn
  $settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries -ExecutionTimeLimit (New-TimeSpan -Seconds 0) `
    -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1)
  $principal = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" `
    -LogonType Interactive
  Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger `
    -Settings $settings -Principal $principal `
    -Description "FareAlert low-fare monitor Web UI (http://127.0.0.1:8765)" | Out-Null
  $check = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
  if ($check) {
    Write-Output ("INSTALLED autostart task $TaskName -> " + $RepoDir)
  } else { Write-Output "FAIL: task registration denied (try -Mode registry)"; exit 1 }
}
