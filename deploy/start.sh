#!/bin/sh
# single container: scheduler loop (background) + webui (foreground, PID 1)
# interval controlled by config.json schedule.interval_minutes (default 45min)
mkdir -p /app/data
python -X utf8 main.py --loop &
POLLER_PID=$!
python -X utf8 webui.py &
WEB_PID=$!
echo "[start] poller=$POLLER_PID webui=$WEB_PID"
# shell stays PID 1: forward TERM to both children, then exit (docker stop)
trap "kill $POLLER_PID $WEB_PID 2>/dev/null; exit" TERM INT
wait $WEB_PID
