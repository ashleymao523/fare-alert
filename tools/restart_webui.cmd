@echo off
setlocal
cd /d "%~dp0.."
powershell -NoProfile -Command "Get-NetTCPConnection -LocalPort 8765 -State Listen -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess -Unique | ForEach-Object { Stop-Process -Id $_ -Force -ErrorAction SilentlyContinue }"
powershell -NoProfile -Command "Start-Sleep -Milliseconds 800"
powershell -NoProfile -Command "Start-Process python -ArgumentList webui.py -WorkingDirectory '%~dp0..' -WindowStyle Hidden"
endlocal
