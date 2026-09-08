# Register Windows Task Scheduler job: run FareAlert every 45 minutes.
$ErrorActionPreference = "Stop"
$pyw = (Get-Command pythonw -ErrorAction SilentlyContinue).Source
if (-not $pyw) { $pyw = (Get-Command python).Source }
$script = (Resolve-Path (Join-Path $PSScriptRoot "..\main.py")).Path
$tr = '"' + $pyw + '" -X utf8 "' + $script + '" --once'
schtasks /Create /TN "FareAlert" /TR $tr /SC MINUTE /MO 45 /F
Write-Host "Task created. Remove anytime with deploy\remove_task.ps1"
