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
CMD ["/start.sh"]
