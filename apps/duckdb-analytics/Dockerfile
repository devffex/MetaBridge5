# ==========================================
# STAGE 1: Debian Builder for DuckDB wheel
# ==========================================
FROM python:3.12-slim AS duckdb-extractor

COPY --from=ghcr.io/astral-sh/uv:0.4.30 /uv /usr/bin/

WORKDIR /build
RUN uv pip install --system --no-cache --target=/duckdb-pkg 'duckdb==2.0.0' && \
    rm -rf /duckdb-pkg/duckdb/experimental

# ==========================================
# STAGE 2: Alpine C-shim compiler for res_init
# ==========================================
FROM alpine:3.20 AS shim-builder

RUN apk add --no-cache gcc musl-dev && \
    echo 'int __res_init(void) { return 0; }' > /tmp/res_init.c && \
    gcc -shared -fPIC -O2 /tmp/res_init.c -o /usr/lib/libres_init.so

# ==========================================
# STAGE 3: Alpine Builder for Python Dependencies
# ==========================================
FROM alpine:3.20 AS alpine-builder

RUN apk add --no-cache python3 py3-pip binutils

COPY --from=ghcr.io/astral-sh/uv:0.4.30 /uv /usr/bin/

WORKDIR /build
COPY apps/duckdb-analytics/pyproject.toml ./

ENV UV_PROJECT_ENVIRONMENT=/opt/analytics-venv
RUN uv venv /opt/analytics-venv && \
    uv pip install --python /opt/analytics-venv --no-cache \
        'fastapi>=0.110.0' \
        'uvicorn>=0.28.0' \
        'httptools>=0.6.0' \
        'uvloop>=0.19.0' \
        'pytz>=2024.1'

# Copy DuckDB package from duckdb-extractor
COPY --from=duckdb-extractor /duckdb-pkg/ /opt/analytics-venv/lib/python3.12/site-packages/

# Prune tests, caches, and type annotations
RUN find /opt/analytics-venv -type d \( -name "tests" -o -name "test" -o -name "__pycache__" \) -exec rm -rf {} + && \
    find /opt/analytics-venv -name "*.pyi" -delete && \
    find /opt/analytics-venv -name "*.so" -exec strip --strip-unneeded {} + 2>/dev/null || true

# ==========================================
# STAGE 4: Final Alpine Analytics Runtime
# ==========================================
FROM alpine:3.20 AS metabridge5-duckdb-analytics

RUN apk add --no-cache python3 tini gcompat ca-certificates && \
    find /usr/lib/python3.12 -type d \( -name "__pycache__" -o -name "ensurepip" -o -name "pydoc_data" -o -name "lib2to3" -o -name "turtledemo" -o -name "unittest" -o -name "test" -o -name "tests" \) -exec rm -rf {} + && \
    find /usr/lib/python3.12 -type f \( -name "*.pyc" -o -name "*.pyo" \) -delete && \
    adduser -D -u 1000 -h /app appuser && \
    mkdir -p /data/parquet /tmp/analytics /app && \
    chown -R appuser:appuser /data /tmp/analytics /app

WORKDIR /app

# Copy C-shim library
COPY --from=shim-builder /usr/lib/libres_init.so /usr/lib/libres_init.so

# Copy isolated virtual environment
COPY --from=alpine-builder /opt/analytics-venv /opt/analytics-venv

# Re-link venv python binary to Alpine system python3
RUN ln -sf /usr/bin/python3 /opt/analytics-venv/bin/python && \
    ln -sf /usr/bin/python3 /opt/analytics-venv/bin/python3

# Copy application source code
COPY --chown=appuser:appuser apps/duckdb-analytics/app/ /app/app/

ENV PATH="/opt/analytics-venv/bin:$PATH" \
    PYTHONPATH="/opt/analytics-venv/lib/python3.12/site-packages" \
    PYTHONUNBUFFERED=1 \
    LD_PRELOAD="/usr/lib/libres_init.so /lib/libgcompat.so.0" \
    METABRIDGE5_PARQUET_DIR=/data/parquet \
    DUCKDB_THREADS=2 \
    DUCKDB_MEMORY_LIMIT=2GB

USER appuser
EXPOSE 8005

HEALTHCHECK --interval=15s --timeout=5s --start-period=5s --retries=3 \
    CMD ["wget", "-q", "--spider", "http://127.0.0.1:8005/health"]

ENTRYPOINT ["/sbin/tini", "--"]
CMD ["/opt/analytics-venv/bin/python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8005"]
