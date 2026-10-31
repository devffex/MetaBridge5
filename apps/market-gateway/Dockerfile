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
# STAGE 2: Market Node Runtime
# ==========================================
FROM metabridge5-base:latest

USER root

# Install minimal native Python 3 runtime (no pip, no setuptools, no build tools)
RUN apk add --no-cache python3

# Copy isolated pre-built gateway virtualenv
COPY --from=gateway-builder /opt/gateway-venv /opt/gateway-venv

# Setup gateway workspace
RUN mkdir -p /home/wine/app/market-gateway && \
    chown -R wine:wine /home/wine/app/market-gateway

# Copy gateway application source code
COPY --chown=wine:wine apps/market-gateway/app/ /home/wine/app/market-gateway/app/

# Inject supervisord configuration
COPY --chown=wine:wine apps/market-gateway/supervisord.conf /etc/supervisor/conf.d/market-gateway.conf

EXPOSE 8000

# Entrypoint and CMD inherited from metabridge5-base: /sbin/tini -- /opt/metabridge5/entrypoint.sh
