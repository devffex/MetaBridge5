FROM savisor-base:latest

# Copy the pipeline codebase
COPY --chown=wine:wine apps/data-pipeline/src/ /home/wine/app/pipeline/

# Copy pipeline-specific supervisord configuration
COPY --chown=wine:wine apps/data-pipeline/supervisord.conf /etc/supervisor/conf.d/pipeline.conf
