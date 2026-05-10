FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY backend /app/backend
COPY ai_system /app/ai_system
COPY metadata /app/metadata
COPY contracts /app/contracts
COPY artifacts /app/artifacts
COPY data /app/data

WORKDIR /app/backend
