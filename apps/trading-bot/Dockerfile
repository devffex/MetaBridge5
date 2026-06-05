FROM savisor-base:latest

# Switch to root to perform file cleanups and copy files
USER root

# Clean up wheels to keep this child image size minimal
RUN rm -rf /home/wine/.wine/drive_c/wheels

# Copy the bot codebase
COPY --chown=wine:wine apps/trading-bot/src/ /home/wine/app/bot/

# Copy bot-specific supervisord configuration
COPY --chown=wine:wine apps/trading-bot/supervisord.conf /etc/supervisor/conf.d/bot.conf

# Switch back to the standard run user
USER wine
WORKDIR /home/wine
