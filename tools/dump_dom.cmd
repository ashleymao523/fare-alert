@echo off
setlocal
set CWD=%~dp0..
set EDGE=C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe
set UDD=%CWD%\data\edge_prof_tmp
"%EDGE%" --headless --disable-gpu --no-first-run --user-data-dir="%UDD%" --virtual-time-budget=12000 --dump-dom "http://127.0.0.1:8765/?v=8" > "%CWD%\data\ui_dom.html" 2>nul
endlocal
