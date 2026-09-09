@echo off
setlocal
set CWD=%~dp0..
set EDGE=C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe
set UDD=%CWD%\data\edge_prof_qshot
"%EDGE%" --headless --disable-gpu --no-first-run --user-data-dir="%UDD%" --virtual-time-budget=15000 --window-size=420,900 --screenshot="%CWD%\data\qunar_list.png" "%~1" 2>nul
endlocal

