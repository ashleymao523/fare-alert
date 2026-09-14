# syntax=docker/dockerfile:1
FROM python:3.13-slim

WORKDIR /app
ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    FAREALERT_HOST=0.0.0.0 \
    FAREALERT_PORT=8765

# mirror arg keeps builds fast behind GFW; override with
# --build-arg PIP_INDEX_URL=https://pypi.org/simple
ARG PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple
COPY requirements.txt ./
RUN pip install --no-cache-dir -i ${PIP_INDEX_URL} -r requirements.txt

# web/dist is committed, so the image needs zero Node tooling; the
# in-process revive supervisor spawns `main.py --loop` automatically
# when no worker heartbeat exists (same model as the Windows box)
COPY . .
EXPOSE 8765
HEALTHCHECK --interval=60s --timeout=10s --start-period=30s \
  CMD ["python", "-c", "import urllib.request;urllib.request.urlopen('http://127.0.0.1:8765/api/health', timeout=8)"]
# v0.77: all-in-one - webui + crawler loop in one container (FA_ROLE
# env: all | webui | worker). Crawler loop sediments the sched-board
# dow library daily, which is what makes exact departure times appear.
CMD ["python", "run_all.py"]
