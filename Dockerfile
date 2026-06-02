# ==========================================
# STAGE 1: Font Builder
# ==========================================
FROM alpine:latest AS font-builder

RUN apk add --no-cache --repository http://dl-cdn.alpinelinux.org/alpine/edge/community \
    msttcorefonts-installer \
    && update-ms-fonts

# ==========================================
# STAGE 2: Python Builder (Offline Windows Packages)
# ==========================================
FROM alpine:latest AS python-builder

RUN apk add --no-cache python3 py3-pip curl unzip

# 1. Download and extract Windows Python embeddable
RUN curl -L https://www.python.org/ftp/python/3.11.9/python-3.11.9-embed-amd64.zip -o /tmp/python.zip && \
    mkdir -p /tmp/python/Lib/site-packages && \
    unzip /tmp/python.zip -d /tmp/python && \
    rm /tmp/python.zip

# 2. Enable site-packages in Windows Python
RUN sed -i 's/#import site/import site/' /tmp/python/python311._pth

# 3. Download all required Windows amd64 wheels (including pip, setuptools, and wheel)
RUN mkdir -p /tmp/wheels && \
    pip download --dest /tmp/wheels \
    --only-binary=:all: \
    --platform win_amd64 \
    --python-version 3.11 \
    --implementation cp \
    --abi cp311 \
    fastapi uvicorn pydantic numpy pandas MetaTrader5 pip setuptools wheel tzdata pytz colorama

# 4. Bootstrap pip, setuptools, and wheel offline by unzipping their wheels into site-packages
RUN unzip -o /tmp/wheels/pip-*.whl -d /tmp/python/Lib/site-packages/ && \
    unzip -o /tmp/wheels/setuptools-*.whl -d /tmp/python/Lib/site-packages/ && \
    unzip -o /tmp/wheels/wheel-*.whl -d /tmp/python/Lib/site-packages/



# ==========================================
# STAGE 4: Final Runtime Image
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
    wine \
    curl \
    unzip \
    gnutls \
    ca-certificates \
    tzdata \
    xdotool \
    libfaketime

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

# Copy supervisord configuration and helper scripts
COPY supervisord/supervisord.conf /etc/supervisord.conf
COPY --chown=wine:wine supervisord/dismiss_dialogs.sh /home/wine/dismiss_dialogs.sh
RUN chmod +x /home/wine/dismiss_dialogs.sh

# Copy portable MetaTrader 5 from host
COPY --chown=wine:wine MetaTrader5/ /home/wine/.wine/drive_c/MetaTrader5/

# Configure system timezone name for Wine's timezone auto-detection
RUN echo "UTC" > /etc/timezone

# Clean up any pre-baked host-specific terminal license and account cache to ensure clean broker TLS handshakes
RUN rm -f /home/wine/.wine/drive_c/MetaTrader5/Config/terminal.lic \
          /home/wine/.wine/drive_c/MetaTrader5/Config/accounts.dat

# Perform setup tasks as the wine user
USER wine
WORKDIR /home/wine

# Initialize Wine Prefix and apply the modern flat light theme, and register cryptographic providers
RUN wineboot --init && \
    wine reg add "HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Themes\\Personalize" /v AppsUseLightTheme /t REG_DWORD /d 1 /f && \
    wine reg add "HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Themes\\Personalize" /v SystemUsesLightTheme /t REG_DWORD /d 1 /f && \
    wine reg add "HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\ThemeManager" /v ThemeActive /t REG_SZ /d "1" /f && \
    wine reg add "HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\ThemeManager" /v DllName /t REG_SZ /d "C:\\windows\\resources\\themes\\light\\light.msstyles" /f && \
    wine reg add "HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\ThemeManager" /v ColorName /t REG_SZ /d "NormalColor" /f && \
    wine reg add "HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\ThemeManager" /v SizeName /t REG_SZ /d "NormalSize" /f && \
    wine reg add "HKLM\\Software\\Microsoft\\Cryptography\\Defaults\\Provider Types\\Type 024" /v Name /t REG_SZ /d "Microsoft Enhanced RSA and AES Cryptographic Provider" /f && \
    wine reg add "HKLM\\Software\\Microsoft\\Cryptography\\Defaults\\Provider Types\\Type 024" /v TypeName /t REG_SZ /d "RSA Full and AES" /f && \
    wine reg add "HKLM\\Software\\Microsoft\\Cryptography\\Defaults\\Provider\\Microsoft Enhanced RSA and AES Cryptographic Provider" /v "Image Path" /t REG_SZ /d "rsaenh.dll" /f && \
    wine reg add "HKLM\\Software\\Microsoft\\Cryptography\\Defaults\\Provider\\Microsoft Enhanced RSA and AES Cryptographic Provider" /v Type /t REG_DWORD /d 24 /f && \
    wine reg add "HKLM\\Software\\Microsoft\\Cryptography\\Defaults\\Provider\\Microsoft Enhanced RSA and AES Cryptographic Provider" /v SigInFile /t REG_DWORD /d 0 /f && \
    wineserver -w

# Copy the prepared Windows Python and pre-downloaded wheels from Stage 2
COPY --chown=wine:wine --from=python-builder /tmp/python/ /home/wine/.wine/drive_c/python/
COPY --chown=wine:wine --from=python-builder /tmp/wheels/ /home/wine/.wine/drive_c/wheels/

# Install the dependencies offline in Wine Python with no-cache-dir to minimize size
RUN wine C:\\python\\python.exe -m pip install --no-cache-dir --no-index --find-links C:\\wheels \
    fastapi uvicorn pydantic numpy pandas MetaTrader5

# Clean up wheels to reduce final image size
RUN rm -rf /home/wine/.wine/drive_c/wheels

# Copy and run certificate importer to register Alpine root CAs inside Wine
COPY --chown=wine:wine import_certs.py /home/wine/.wine/drive_c/import_certs.py
RUN wine C:\\python\\python.exe C:\\import_certs.py && rm /home/wine/.wine/drive_c/import_certs.py && wineserver -w

# Copy the API codebase into /home/wine/app
COPY --chown=wine:wine api/ /home/wine/app/api/

EXPOSE 5900 8000

ENTRYPOINT ["/usr/bin/supervisord", "-c", "/etc/supervisord.conf"]
