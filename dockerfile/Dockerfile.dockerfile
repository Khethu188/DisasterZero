
# ─────────────────────────────────────────────────────────────
# Dockerfile
# DisasterZero — Container Image
# ─────────────────────────────────────────────────────────────
# Multi-stage build for minimal production image.
# ─────────────────────────────────────────────────────────────

# ── Stage 1: Builder ──
FROM python:3.11-slim AS builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc && \
    rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# ── Stage 2: Production ──
FROM python:3.11-slim AS production

LABEL maintainer="Khethukuthula <github.com/Khethu188>"
LABEL project="DisasterZero"
LABEL description="Automated Disaster Recovery Testing Platform"

WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /install /usr/local

# Copy application code
COPY src/ src/
COPY dashboard/ dashboard/
COPY scripts/ scripts/
COPY pytest.ini .
COPY requirements.txt .

# Create non-root user
RUN groupadd -r disasterzero && \
    useradd -r -g disasterzero -d /app -s /sbin/nologin disasterzero && \
    mkdir -p reports && \
    chown -R disasterzero:disasterzero /app

USER disasterzero

# Environment
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    ENVIRONMENT=dev

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "from src.config import DisasterZeroConfig; print('healthy')" || exit 1

# Expose Streamlit port
EXPOSE 8501

# Default: run the dashboard
CMD ["python", "-m", "streamlit", "run", "dashboard/app.py", \
     "--server.port=8501", "--server.address=0.0.0.0", \
     "--server.headless=true"]

