FROM savisor-base:latest

USER root

# Install native Python 3 and pip on Alpine
RUN apk add --no-cache python3 py3-pip

# Install Astral-sh uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/bin/

# Install API requirements natively as root (system-wide)
COPY apps/market-gateway/pyproject.toml apps/market-gateway/uv.lock /tmp/
RUN uv pip install --system --break-system-packages --no-cache -r /tmp/pyproject.toml && \
    rm -rf /tmp/pyproject.toml /tmp/uv.lock

# Create directory for gateway code
RUN mkdir -p /home/wine/app/market-gateway && \
    chown -R wine:wine /home/wine/app/market-gateway

USER wine

# Copy gateway source code
COPY --chown=wine:wine apps/market-gateway/app/ /home/wine/app/market-gateway/app/

# Inject supervisord configuration
COPY --chown=wine:wine apps/market-gateway/supervisord.conf /etc/supervisor/conf.d/market-gateway.conf

EXPOSE 8000

# Entrypoint is inherited from savisor-base: /usr/bin/supervisord

