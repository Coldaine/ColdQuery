# Multi-stage build for optimized production image

# Stage 1: Builder
FROM python:3.12-alpine AS builder

WORKDIR /build

# Install build dependencies
RUN apk add --no-cache \
    gcc \
    musl-dev \
    postgresql-dev \
    python3-dev

# Copy dependency files
COPY pyproject.toml ./
COPY coldquery ./coldquery

# Install dependencies (NOT editable - editable install breaks multi-stage builds)
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir .

# Stage 2: Runtime
FROM python:3.12-alpine

WORKDIR /app

# Install runtime dependencies
RUN apk add --no-cache \
    libpq \
    wget \
    && addgroup -g 1000 coldquery \
    && adduser -D -u 1000 -G coldquery coldquery

# Copy installed packages from builder (includes coldquery)
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# NOTE: Do NOT copy coldquery here - it's already in site-packages from pip install
# Having both causes import conflicts where /app/coldquery shadows site-packages

# Switch to non-root user
USER coldquery

# Environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    HOST=0.0.0.0 \
    PORT=19002

# Healthcheck
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD wget --spider -q http://localhost:${PORT}/health || exit 1

# Expose port
EXPOSE 19002

# Run server
CMD ["python", "-m", "coldquery.server", "--transport", "http"]