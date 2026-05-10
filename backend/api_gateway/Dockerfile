FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app/backend

RUN apt-get update && apt-get install -y --no-install-recommends \
    libexpat1 \
    libgdal-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY backend /app/backend
COPY ai_system /app/ai_system
COPY metadata /app/metadata
COPY contracts /app/contracts
COPY migrations /app/migrations
COPY scripts /app/scripts
COPY alembic.ini /app/alembic.ini

WORKDIR /app/backend
