@echo off
rem synchronous dumper: python waits on each Edge run, so the merged
rem data/ui_dom.html is never observed half-written (old ping-sleep
rem cmd let ui_check read a partial file -> flaky v0.13 reverse FAIL)
python "%~dp0dump_dom.py"
