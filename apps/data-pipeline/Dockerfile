FROM savisor-base:latest

# Switch to root to perform file cleanups and copy files
USER root

# Clean up wheels to keep this child image size minimal
RUN rm -rf /home/wine/.wine/drive_c/wheels

# Copy the pipeline codebase
COPY --chown=wine:wine apps/data-pipeline/src/ /home/wine/app/pipeline/

# Copy pipeline-specific supervisord configuration
COPY --chown=wine:wine apps/data-pipeline/supervisord.conf /etc/supervisor/conf.d/pipeline.conf

# Switch back to the standard run user
USER wine
WORKDIR /home/wine
