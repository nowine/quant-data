# =============================================================================
# quant-data collector — unified container image for all 4 collectors.
#
# Public entrypoint (called by OpenClaw cron via podman run):
#   /app/scripts/entrypoint.sh --script {daily|weekly|monthly|quarterly} \
#                              [--mode {close|morning}] \
#                              --config /data/config/etf_config.json \
#                              [--extra-holdings JSON]
#
# Volumes:
#   /data  → /root/secureshare/files/ETF轮动分析框架/  (CSV/JSON output + config)
#
# Build context: project root (Dockerfile is at projects/quant-data/Dockerfile).
# =============================================================================

# Stage 1: builder — install pinned deps
FROM python:3.11-slim AS builder
WORKDIR /app
COPY requirements.txt .
# Pin exact versions (per MEMORY #11 — akshare 1.x has had breaking changes).
# Source of truth: host's `pip show akshare` (1.18.60) + Dockerfile build logs.
# When bumping, re-test end-to-end (see docs/DEPLOY.md step 4).
RUN pip install --no-cache-dir \
    akshare==1.18.60 \
    pandas==2.2.3 \
    pydantic==2.9.2 \
    requests==2.32.3 \
    jsonschema==4.23.0

# Stage 2: runner — minimal runtime
FROM python:3.11-slim AS runner
WORKDIR /app

# Copy source tree (the 4 collector modules + supporting libs)
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY src/ ./src/
COPY scripts/ ./scripts/
COPY examples/ ./examples/

# Non-root user for defense-in-depth (rootless Podman recommended for production)
RUN useradd -m -u 1000 appuser && \
    chmod +x scripts/entrypoint.sh && \
    mkdir -p /data && chown appuser:appuser /data
USER appuser

# PYTHONPATH=. so `from src import config` works
ENV PYTHONPATH=/app

# Default to daily/close — cron args override via podman run --args
ENTRYPOINT ["bash", "/app/scripts/entrypoint.sh"]
CMD ["--script", "daily", "--mode", "close"]
