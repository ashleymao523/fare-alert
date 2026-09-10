FROM python:3.12-slim

WORKDIR /app
ENV PYTHONUNBUFFERED=1 \
    FAREALERT_HOST=0.0.0.0 \
    FAREALERT_PORT=8765

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY core core
COPY webui webui
COPY tools tools
COPY deploy deploy
COPY main.py webui.py mcp_server.py config.example.json ./

VOLUME ["/app/data"]
EXPOSE 8765
ENTRYPOINT ["sh", "deploy/docker-entrypoint.sh"]
