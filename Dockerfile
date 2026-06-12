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

# Copy frontend assets (served directly by FastAPI StaticFiles).
COPY frontend/ ./frontend/

# Expose the default port.
EXPOSE 8000

# Health check so container orchestrators know when the app is ready.
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/health')"

# Run from the backend directory so relative data paths resolve correctly.
WORKDIR /app/backend
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
