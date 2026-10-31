# ==========================================
# STAGE 1: Gateway Dependency Builder
# ==========================================
FROM alpine:3.20 AS gateway-builder

RUN apk add --no-cache python3 py3-pip binutils

# Install uv binary
COPY --from=ghcr.io/astral-sh/uv:0.4.30 /uv /uvx /usr/bin/

WORKDIR /build

# Copy locked requirements
COPY apps/market-gateway/pyproject.toml apps/market-gateway/uv.lock ./

# Create virtual environment and install frozen dependencies directly into /opt/gateway-venv
ENV UV_PROJECT_ENVIRONMENT=/opt/gateway-venv
RUN uv sync --frozen --no-dev --no-install-project

# Prune botocore data (keep only s3, sts, sso, sso-oidc and core endpoints)
RUN find /opt/gateway-venv/lib/python3.12/site-packages/botocore/data -mindepth 1 -maxdepth 1 -type d \
        ! -name "s3" ! -name "sts" ! -name "sso" ! -name "sso-oidc" -exec rm -rf {} + && \
    # Remove tests, __pycache__, type stubs and dist-info files
    find /opt/gateway-venv -type d \( -name "tests" -o -name "test" -o -name "__pycache__" -o -name "*.dist-info" \) -exec rm -rf {} + && \
    find /opt/gateway-venv -name "*.pyi" -delete && \
    # Strip debugging symbols from shared objects
    find /opt/gateway-venv -name "*.so" -exec strip --strip-unneeded {} + 2>/dev/null || true


# ==========================================
# STAGE 2: Market Gateway Standalone Runtime
# ==========================================
FROM alpine:3.20 AS metabridge5-market-gateway

RUN apk add --no-cache python3 tini ca-certificates && \
    find /usr/lib/python3.12 -type d \( -name "__pycache__" -o -name "ensurepip" -o -name "pydoc_data" -o -name "lib2to3" -o -name "turtledemo" -o -name "unittest" -o -name "test" -o -name "tests" \) -exec rm -rf {} + && \
    find /usr/lib/python3.12 -type f \( -name "*.pyc" -o -name "*.pyo" \) -delete && \
    adduser -D -u 1000 -h /home/app app && \
    mkdir -p /data && \
    chown -R app:app /data /home/app

WORKDIR /home/app

# Copy isolated pre-built gateway virtualenv
COPY --from=gateway-builder /opt/gateway-venv /opt/gateway-venv

# Copy gateway application source code
COPY --chown=app:app apps/market-gateway/app/ /home/app/app/

ENV PATH="/opt/gateway-venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    METABRIDGE5_DATA_DIR=/data \
    MT5_GRPC_SERVER=metabridge5-core:50051

USER app
EXPOSE 8000

HEALTHCHECK --interval=15s --timeout=5s --start-period=10s --retries=3 \
    CMD ["wget", "-q", "--spider", "http://127.0.0.1:8000/health"]

ENTRYPOINT ["/sbin/tini", "--"]
CMD ["/opt/gateway-venv/bin/python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
