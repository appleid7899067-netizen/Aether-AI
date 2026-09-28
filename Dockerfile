# =============================================================================
# Aether AI - headless API image (Render / Railway / Fly.io / any container host)
# -----------------------------------------------------------------------------
# Desktop-only dependencies (PyQt6, pyautogui, pynput, pyaudio, torch, openvino)
# are intentionally NOT installed: they have no display inside a container.  The
# application detects the headless environment and disables those routes, while
# chat, memory, voice synthesis, bug-bounty recon, monitoring and n8n keep
# working.
#
#   docker build -t aether-ai .
#   docker run -p 8000:8000 --env-file .env aether-ai
# =============================================================================
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Runtime helpers: curl for the health check, tesseract for OCR,
# libglib2.0 for OpenCV, and the usual build tooling for wheels.
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        curl \
        git \
        tesseract-ocr \
        libglib2.0-0 \
        libgomp1 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements-server.txt .

RUN pip install --upgrade pip && pip install -r requirements-server.txt

COPY . .

RUN mkdir -p /app/data /app/logs

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -fsS http://localhost:${PORT:-8000}/health || exit 1

# Render / Heroku style hosts inject $PORT
CMD uvicorn src.api.main:app --host 0.0.0.0 --port ${PORT:-8000}
