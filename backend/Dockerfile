# backend/Dockerfile
FROM python:3.11-slim

WORKDIR /app
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1
ENV PIP_DEFAULT_TIMEOUT=100

# Small system deps useful for healthchecks and building wheels + OCR
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
      curl \
      build-essential \
      gcc \
      libpq-dev \
      tesseract-ocr \
    && rm -rf /var/lib/apt/lists/*

# Install Python deps (upgrade pip and retry to reduce transient failures)
COPY requirements.txt .
RUN pip install --upgrade pip setuptools wheel && \
    for i in 1 2 3; do \
      pip install --no-cache-dir -r requirements.txt && break || \
      (echo "pip install failed, retrying ($i)..." && sleep 5); \
    done

# Copy application code (app/ should contain worker/worker.py and all app modules)
COPY app ./app
COPY .env.example .env

# Create uploads dir used by the app
RUN mkdir -p /data/uploads

EXPOSE 8000

# Default command for backend; worker will override command in docker-compose
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
