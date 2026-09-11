@echo off
setlocal
set CWD=%~dp0..
set EDGE=C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe
set UDD=%CWD%\data\edge_prof_shot
"%EDGE%" --headless --disable-gpu --no-first-run --user-data-dir="%UDD%" --virtual-time-budget=12000 --window-size=1440,2600 --screenshot="%CWD%\data\ui_v08b.png" "http://127.0.0.1:8765/?v=8" 2>nul
endlocal
@echo off
setlocal
set CWD=%~dp0..
set EDGE=C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe
set UDD=%CWD%\data\edge_prof_shot
"%EDGE%" --headless --disable-gpu --no-first-run --user-data-dir="%UDD%" --virtual-time-budget=12000 --window-size=1440,2600 --screenshot="%CWD%\data\ui_v024.png" "http://127.0.0.1:8765/?v=24#weekly" 2>nul
"%EDGE%" --headless --disable-gpu --no-first-run --user-data-dir="%UDD%" --virtual-time-budget=12000 --window-size=1440,2600 --screenshot="%CWD%\data\ui_v025.png" "http://127.0.0.1:8765/?v=25#deals" 2>nul
endlocal
