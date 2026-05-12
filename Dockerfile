FROM python:3.12-slim-bookworm

LABEL org.opencontainers.image.title="devops1-breast-cancer-api"
LABEL org.opencontainers.image.description="FastAPI + логрег"

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

COPY requirements-docker.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

COPY config.ini .
COPY src ./src
COPY scripts ./scripts
COPY experiments ./experiments

EXPOSE 8000

CMD ["uvicorn", "src.api:app", "--host", "0.0.0.0", "--port", "8000"]
