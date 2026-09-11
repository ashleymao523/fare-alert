# Install/uninstall FareAlert logon autostart for webui AND worker.
# Usage:
#   powershell -NoProfile -ExecutionPolicy Bypass -File tools/install_autostart.ps1
#   powershell ... -File tools/install_autostart.ps1 -Components webui
#   powershell ... -File tools/install_autostart.ps1 -Uninstall
param(
  [switch]$Uninstall,
  [ValidateSet("registry", "task")]
  [string]$Mode = "registry",
  [ValidateSet("webui", "worker")]
  [string[]]$Components = @("webui", "worker"),
  [string]$RepoDir = (Split-Path $PSScriptRoot -Parent),
  [string]$RunKey = "HKCU:\Software\Microsoft\Windows\CurrentVersion\Run"
)
$ErrorActionPreference = "Stop"

# entry-name suffix + logon wrapper per component
$CompMap = @{
  webui  = @{ suffix = "WebUI";  wrapper = "autostart_webui.ps1" }
  worker = @{ suffix = "Worker"; wrapper = "autostart_worker.ps1" }
}

if ($Uninstall) {
  $removed = @()
  foreach ($c in @("webui", "worker")) {   # sweep both, ignore -Components
    $name = "FareAlert" + $CompMap[$c].suffix
    $t = Get-ScheduledTask -TaskName $name -ErrorAction SilentlyContinue
    if ($t) {
      Unregister-ScheduledTask -TaskName $name -Confirm:$false
      $removed += "task:$name"
    }
    $rk = Get-Item $RunKey -ErrorAction SilentlyContinue
    if ($rk -and $rk.GetValue($name)) {
      Remove-ItemProperty -Path $RunKey -Name $name
      $removed += "registry:$name"
    }
  }
  if ($removed) { Write-Output ("REMOVED " + ($removed -join ", ")) }
  else { Write-Output "NOOP: no autostart entries found" }
  exit 0
}

foreach ($c in $Components) {
  $meta = $CompMap[$c]
  $name = "FareAlert" + $meta.suffix
  # wrappers self-guard: skip launch when already listening/running
  $wrapper = Join-Path $RepoDir ("tools\" + $meta.wrapper)
  $cmdLine = 'powershell.exe -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "{0}"' -f $wrapper
  if ($Mode -eq "registry") {
    # Preferred: per-user HKCU Run key (no admin, no task-scheduler policy)
    if (-not (Test-Path $RunKey)) { New-Item -Path $RunKey -Force | Out-Null }
    Set-ItemProperty -Path $RunKey -Name $name -Value $cmdLine
    if ((Get-ItemProperty $RunKey).$name -ne $cmdLine) {
      Write-Output "FAIL: registry write did not stick for $name"; exit 1
    }
    Write-Output ("INSTALLED HKCU Run entry $name -> " + $RepoDir)
  } else {
    # Fallback: scheduled task (needs elevation on locked-down hosts)
    $existing = Get-ScheduledTask -TaskName $name -ErrorAction SilentlyContinue
    if ($existing) { Unregister-ScheduledTask -TaskName $name -Confirm:$false }
    $action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument $cmdLine
    $trigger = New-ScheduledTaskTrigger -AtLogOn
    $settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries `
      -DontStopIfGoingOnBatteries -ExecutionTimeLimit (New-TimeSpan -Seconds 0) `
      -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1)
    $principal = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" `
      -LogonType Interactive
    Register-ScheduledTask -TaskName $name -Action $action -Trigger $trigger `
      -Settings $settings -Principal $principal `
      -Description "FareAlert $c autostart ($($meta.wrapper))" | Out-Null
    if (-not (Get-ScheduledTask -TaskName $name -ErrorAction SilentlyContinue)) {
      Write-Output "FAIL: task registration denied for $name (try -Mode registry)"
      exit 1
    }
    Write-Output ("INSTALLED autostart task $name -> " + $RepoDir)
  }
}
Write-Output "Next logon auto-starts the selected components (wrappers skip if already up)."
