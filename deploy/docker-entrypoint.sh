#!/bin/sh
# 单容器同时跑: 轮询采集(python main.py --loop) + Web UI(webui.py)
# 轮询间隔由 config.json schedule.interval_minutes 控制(默认45分钟,红线>=30)
mkdir -p /app/data
python main.py --loop &
POLLER_PID=$!
echo "[entrypoint] poller started pid=$POLLER_PID"
trap "kill $POLLER_PID 2>/dev/null; exit" TERM INT
exec python webui.py
