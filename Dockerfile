# Multi-stage build for optimeret Docker image
FROM python:3.11-slim as builder

# Installer build dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    libffi-dev \
    libssl-dev \
    && rm -rf /var/lib/apt/lists/*

# Kopier requirements og installer Python dependencies
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# Final stage
FROM python:3.11-slim

# Installer runtime dependencies for video processing
RUN apt-get update && apt-get install -y \
    ffmpeg \
    libmagic1 \
    && rm -rf /var/lib/apt/lists/*

# Opret non-root bruger
RUN useradd -m -u 1000 appuser && \
    mkdir -p /app/data /app/uploads /app/optimized /app/originals /app/templates /app/static && \
    chown -R appuser:appuser /app

WORKDIR /app

# Kopier Python dependencies fra builder
COPY --from=builder --chown=appuser:appuser /root/.local /home/appuser/.local

# Kopier applikationsfiler
COPY --chown=appuser:appuser app_docker.py ./app.py
COPY --chown=appuser:appuser templates/ ./templates/
COPY --chown=appuser:appuser static/ ./static/

# Kopier mediefiler (oprettes hvis de ikke findes)

# Sæt environment variabler
ENV FLASK_APP=app.py
ENV PYTHONUNBUFFERED=1
ENV PATH=/home/appuser/.local/bin:$PATH
ENV PORT=45764

# Skift til non-root bruger
USER appuser

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD python -c "import requests; r = requests.get('http://localhost:45764/health'); exit(0 if r.status_code == 200 else 1)"

# Expose port
EXPOSE 45764

# Start command
CMD ["python", "app.py"]