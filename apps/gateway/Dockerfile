FROM savisor-base:latest

# Switch to wine user to perform package installations inside Wine Python
USER wine

# Install API-specific dependencies offline using wheels cached in the base image
RUN wine C:\\python\\python.exe -m pip install --no-cache-dir --no-index --find-links C:\\wheels \
    fastapi uvicorn pydantic

# Switch to root to perform file cleanups and copy files
USER root

# Clean up wheels to keep this child image size minimal
RUN rm -rf /home/wine/.wine/drive_c/wheels

# Copy the API codebase
COPY --chown=wine:wine apps/gateway/api/ /home/wine/app/api/

# Copy gateway-specific supervisord configuration
COPY --chown=wine:wine apps/gateway/supervisord.conf /etc/supervisor/conf.d/gateway.conf

# Switch back to the standard run user
USER wine
WORKDIR /home/wine

EXPOSE 5900 8000
