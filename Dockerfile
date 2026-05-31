FROM alpine:latest

# Install general purpose dependencies, supervisor, and VNC
RUN apk add --no-cache --repository http://dl-cdn.alpinelinux.org/alpine/edge/community \
    bash \
    curl \
    xvfb \
    freetype \
    fontconfig \
    msttcorefonts-installer \
    supervisor \
    x11vnc \
    && update-ms-fonts \
    && fc-cache -f

# Install Wine from the Alpine community repository
RUN apk add --no-cache --repository http://dl-cdn.alpinelinux.org/alpine/edge/community wine

# Set up user and environment variables for Wine
ENV WINEPREFIX=/home/wine/.wine
ENV WINEARCH=win64
ENV DISPLAY=:1
ENV WINEDLLOVERRIDES="mscoree=disabled"

# Create wine user and workspace
RUN adduser -D -u 1000 wine && \
    mkdir -p /home/wine/.wine && \
    chown -R wine:wine /home/wine

# Copy supervisord configuration
COPY supervisord/supervisord.conf /etc/supervisord.conf

# Copy portable MetaTrader 5 into the Wine C: drive
COPY --chown=wine:wine MetaTrader5/ /home/wine/.wine/drive_c/MetaTrader5/

USER wine
WORKDIR /home/wine

EXPOSE 5900

ENTRYPOINT ["/usr/bin/supervisord", "-c", "/etc/supervisord.conf"]
