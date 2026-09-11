# fare-alert: scheduler + webui in one container (single-user deployment)
# build:  docker build -t fare-alert .
# run:    docker compose up -d   (see docker-compose.yml)
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 PYTHONUTF8=1

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY core/ core/
COPY tools/ tools/
COPY webui/ webui/
COPY main.py webui.py ./

# start.sh keeps scheduler (loop mode) + webui in one process tree
COPY deploy/start.sh /start.sh
RUN chmod +x /start.sh

VOLUME /app/data
EXPOSE 8765

# v0.32: self-healing deploy - compose/docker restart the container when
# the panel stops answering; python:slim has no wget, use stdlib urllib
HEALTHCHECK --interval=60s --timeout=10s --start-period=90s --retries=3 \
    CMD python -c "import urllib.request;urllib.request.urlopen('http://127.0.0.1:8765/api/snapshot', timeout=8)" || exit 1

CMD ["/start.sh"]
