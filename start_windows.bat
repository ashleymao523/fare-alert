@echo off
chcp 65001 >nul
cd /d %~dp0
echo FareAlert Web UI starting: http://127.0.0.1:8765
start "" /min cmd /c "timeout /t 2 /nobreak >nul & start http://127.0.0.1:8765"
python -X utf8 webui.py
echo.
echo Web UI stopped.
pause

