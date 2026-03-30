# ── Stage 1: install dependencies ────────────────────────────────────
FROM python:3.12-slim AS builder

WORKDIR /app

# Install dependencies into a separate directory
# so we can copy only what we need to the final image
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# ── Stage 2: minimal runtime ──────────────────────────────────────────
FROM python:3.12-slim

WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /install /usr/local

# Copy source files
COPY collector.py main.py ./

# Non-root user for security
RUN useradd -r -u 1001 exporter
USER exporter

EXPOSE 8000

CMD ["python", "main.py"]