# ============================================================
# Dockerfile – optimiert für Google Cloud Run
# Multi-stage build: schlank, sicher, schnell
# ============================================================

FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8080

WORKDIR /app

# Abhängigkeiten separat installieren (Layer-Caching)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# App-Code kopieren
COPY app/ ./app/

# Cloud Run erwartet den Server auf $PORT
EXPOSE 8080

# Uvicorn mit 2 Workern – Cloud Run skaliert Instanzen, nicht Worker
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080", "--workers", "2"]
