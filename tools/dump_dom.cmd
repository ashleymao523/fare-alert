@echo off
setlocal
set CWD=%~dp0..
set EDGE=C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe
rem 三段各用独立 profile, 避免 Edge 单例锁(SingletonLock)偶发吞掉后两段 dump
set UDD1=%CWD%\data\edge_prof_p1
set UDD2=%CWD%\data\edge_prof_p2
set UDD3=%CWD%\data\edge_prof_p3
"%EDGE%" --headless --disable-gpu --no-first-run --user-data-dir="%UDD1%" --virtual-time-budget=12000 --dump-dom "http://127.0.0.1:8765/?v=18#crawl" > "%CWD%\data\ui_dom.html" 2>nul
ping -n 7 127.0.0.1 >nul
"%EDGE%" --headless --disable-gpu --no-first-run --user-data-dir="%UDD2%" --virtual-time-budget=12000 --dump-dom "http://127.0.0.1:8765/?v=18#reverse" >> "%CWD%\data\ui_dom.html" 2>nul
ping -n 7 127.0.0.1 >nul
"%EDGE%" --headless --disable-gpu --no-first-run --user-data-dir="%UDD3%" --virtual-time-budget=12000 --dump-dom "http://127.0.0.1:8765/?v=18#weekly" >> "%CWD%\data\ui_dom.html" 2>nul
endlocal
