# ── Stage 1: Python dependencies ────────────────────────────────────────────
FROM python:3.11-slim AS builder

WORKDIR /app

# Install dependencies into a prefix so we can copy them cleanly.
COPY backend/requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# ── Stage 2: Runtime image ───────────────────────────────────────────────────
FROM python:3.11-slim

WORKDIR /app

# Copy installed packages from builder.
COPY --from=builder /install /usr/local

# Copy backend source and data.
COPY backend/ ./backend/

# Copy frontend next to backend so the app finds it in Docker (/app/backend/frontend).
COPY frontend/ ./backend/frontend/

# Expose the default port.
EXPOSE 8000

# Health check so container orchestrators know when the app is ready.
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/health')"

# Verify static assets are present at build time (fail fast if COPY missed files).
RUN test -f /app/backend/frontend/index.html && test -f /app/backend/frontend/css/style.css

# Run from the backend directory so relative data paths resolve correctly.
WORKDIR /app/backend
ENV FRONTEND_DIR=/app/backend/frontend
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 2"]
