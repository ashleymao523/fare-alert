param(
  [string]$RepoDir = (Split-Path $PSScriptRoot -Parent),
  [switch]$Revert
)
# v0.53: one-shot LAN open/close for phone access (iPhone on same Wi-Fi).
# Toggles config webui.host 0.0.0.0 <-> 127.0.0.1, syncs the firewall
# rule and restarts the webui. -Revert closes everything back down.
$ErrorActionPreference = "Stop"
if ($Revert) { $bind = "127.0.0.1" } else { $bind = "0.0.0.0" }
Set-Location $RepoDir
python -X utf8 -c "import json,sys; p=sys.argv[1]; c=json.load(open(p,encoding='utf-8')); c.setdefault('webui',{})['host']=sys.argv[2]; json.dump(c,open(p,'w',encoding='utf-8'),ensure_ascii=False,indent=2)" config.json $bind
$port = (python -X utf8 -c "import json;print(json.load(open('config.json',encoding='utf-8')).get('webui',{}).get('port',8765))")
if ($Revert) {
  netsh advfirewall firewall delete rule name="FareAlert WebUI" 2>$null | Out-Null
  Write-Output "LAN closed: webui now binds 127.0.0.1 (firewall rule removed)."
} else {
  netsh advfirewall firewall add rule name="FareAlert WebUI" dir=in action=allow protocol=TCP localport=$port | Out-Null
  $ip = (Get-NetIPConfiguration | Where-Object { $_.IPv4DefaultGateway -ne $null } |
    Select-Object -First 1).IPv4Address.IPAddress
  Write-Output ("LAN open: open http://" + $ip + ":" + $port + "/ on your phone (same Wi-Fi).")
}
& powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $RepoDir "tools/restart_webui.ps1") -RepoDir $RepoDir
