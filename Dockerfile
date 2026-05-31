# ==========================================
# STAGE 1: Font Builder
# ==========================================
FROM alpine:latest AS font-builder

RUN apk add --no-cache --repository http://dl-cdn.alpinelinux.org/alpine/edge/community \
    msttcorefonts-installer \
    && update-ms-fonts

# ==========================================
# STAGE 2: Final Runtime Image
# ==========================================
FROM alpine:latest

# Combine apk packages to reduce layer overhead
RUN apk add --no-cache --repository http://dl-cdn.alpinelinux.org/alpine/edge/community \
    bash \
    xvfb \
    freetype \
    fontconfig \
    supervisor \
    x11vnc \
    wine

# Set up user and environment variables for Wine
ENV WINEPREFIX=/home/wine/.wine
ENV WINEARCH=win64
ENV DISPLAY=:1
ENV WINEDLLOVERRIDES="mscoree=disabled"

# Create wine user and workspace
RUN adduser -D -u 1000 wine && \
    mkdir -p /home/wine/.wine && \
    chown -R wine:wine /home/wine

# Copy the compiled Microsoft fonts from Stage 1
COPY --from=font-builder /usr/share/fonts/truetype/msttcorefonts/ /usr/share/fonts/truetype/msttcorefonts/

# Rebuild font cache
RUN fc-cache -f

# Copy supervisord configuration
COPY supervisord/supervisord.conf /etc/supervisord.conf

# Copy portable MetaTrader 5 into the Wine C: drive
COPY --chown=wine:wine MetaTrader5/ /home/wine/.wine/drive_c/MetaTrader5/

# Pre-initialize Wine prefix as the wine user during build
USER wine
WORKDIR /home/wine
RUN Xvfb :1 -screen 0 1024x768x16 & \
    XVFB_PID=$! && \
    sleep 2 && \
    wineboot --init && \
    wineserver -w && \
    kill $XVFB_PID && \
    rm -rf /home/wine/.wine/drive_c/windows/temp/* \
           /home/wine/.wine/drive_c/windows/logs/*

EXPOSE 5900

ENTRYPOINT ["/usr/bin/supervisord", "-c", "/etc/supervisord.conf"]
