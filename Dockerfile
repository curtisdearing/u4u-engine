# ── Stage 1: build dependencies ───────────────────────────────────────────────
# pysam (VCF parsing) requires C build tools and several compression libraries.
# We install them here and discard the layer in the final image.
FROM python:3.11-slim AS builder

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    zlib1g-dev \
    libbz2-dev \
    liblzma-dev \
    libcurl4-openssl-dev \
    libssl-dev \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /build

# Copy only what pip needs to install the engine package.
# engine/pyproject.toml uses where = [".."] so pip must run from /build (repo root).
COPY engine/ engine/
RUN pip install --no-cache-dir --prefix=/install "engine/[vcf]"

# Install FastAPI and uvicorn on top of the engine install
RUN pip install --no-cache-dir --prefix=/install \
    "fastapi>=0.110" \
    "uvicorn[standard]>=0.29" \
    "python-multipart>=0.0.9"


# ── Stage 2: runtime image ────────────────────────────────────────────────────
FROM python:3.11-slim AS runtime

# Runtime libraries needed by pysam (shared objects, not build tools)
RUN apt-get update && apt-get install -y --no-install-recommends \
    zlib1g \
    libbz2-1.0 \
    liblzma5 \
    libcurl4 \
 && rm -rf /var/lib/apt/lists/*

# Copy installed packages from builder
COPY --from=builder /install /usr/local

WORKDIR /app

# Copy application code
COPY engine/ engine/
COPY api.py   api.py

# Copy rsID filter files.
# data/ may be empty at build time — the pipeline handles missing filter files
# gracefully (treats them as empty sets). Populate before deploy or mount as a volume.
COPY data/ data/

# Run as non-root user
RUN useradd --no-create-home --shell /bin/false appuser \
 && chown -R appuser:appuser /app
USER appuser

# Expose the application port
EXPOSE 8000

# Liveness probe: container is healthy when /health returns 200
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"

# Start uvicorn.
# Hampton: set --workers to match CPU count on the K8s node.
# Gunicorn with uvicorn workers is an alternative for multi-process deployments:
#   CMD ["gunicorn", "api:app", "-w", "4", "-k", "uvicorn.workers.UvicornWorker", "--bind", "0.0.0.0:8000"]
CMD ["uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8000"]
