FROM savisor-base:latest

# Copy the bot codebase
COPY --chown=wine:wine apps/trading-bot/src/ /home/wine/app/bot/

# Copy bot-specific supervisord configuration
COPY --chown=wine:wine apps/trading-bot/supervisord.conf /etc/supervisor/conf.d/bot.conf
