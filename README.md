# Savisor Node

Reprenset an light weight and isolated metatrader terminal running under wine in a docker linux container. Which expose different interfaces to interact with the terminal with different protocols and process.

## Image Builder

Each step below shows only the Dockerfile instructions introduced in that stage. The final accumulative Dockerfile is provided at the end.

### Step 1: Define the base image

We use Alpine Linux as the lightweight base image.

```dockerfile
FROM alpine:latest
```

#### Why Build from Scratch

- **Minimal Footprint**: Alpine's base image is only 5MB.
- **Security**: Bare-minimum environment eliminates unnecessary packages and services.
- **Resource Optimization**: No desktop environments, audio servers, or X11 overhead — enables high container density per host.
- **Version Control**: Pinned dependency versions prevent automatic breaking updates.

---

### Step 2: Install general purpose deps and libs

Install basic utilities for automation scripts, downloads, and headless window rendering:

- `bash`: Standard shell for entrypoint scripts.
- `curl`: Fetches external files over network protocols.
- `xvfb`: X Virtual Framebuffer — virtual display server in memory.
- `freetype`: Font-rendering engine for Wine UI text.
- `fontconfig`: System font configuration and customization.
- `msttcorefonts-installer`: Microsoft Core Fonts (Arial, Tahoma, etc.).

```dockerfile
RUN apk add --no-cache --repository http://dl-cdn.alpinelinux.org/alpine/edge/community \
    bash \
    curl \
    xvfb \
    freetype \
    fontconfig \
    msttcorefonts-installer \
    && update-ms-fonts \
    && fc-cache -f
```

---

### Step 3: Install wine

Wine is the compatibility layer that maps Windows system calls to POSIX, allowing Windows applications to run on Linux.

```dockerfile
RUN apk add --no-cache --repository http://dl-cdn.alpinelinux.org/alpine/edge/community wine

ENV WINEPREFIX=/home/wine/.wine
ENV WINEARCH=win64
ENV DISPLAY=:1

RUN adduser -D -u 1000 wine && \
    mkdir -p /home/wine/.wine && \
    chown -R wine:wine /home/wine

USER wine
WORKDIR /home/wine
```

---

### Step 4: Setup supervisord

Supervisord manages the execution lifecycles of multiple runtime processes inside the container.

- **Multi-Process Orchestration**: Starts `Xvfb`, VNC, and Wine in a controlled, prioritized sequence.
- **Process Monitoring & Restarts**: Automatically restarts crashed processes.
- **Graceful Signal Handling**: Intercepts `SIGTERM` to terminate processes cleanly.
- **Unified Log Capture**: Routes all subprocess output to Docker container logs.

Add `supervisor` to the dependency installation in Step 2, then configure:

```dockerfile
# Added to the Step 2 apk add command:
#   supervisor

COPY supervisord/supervisord.conf /etc/supervisord.conf
ENTRYPOINT ["/usr/bin/supervisord", "-c", "/etc/supervisord.conf"]
```

#### Supervisord Configuration (`supervisord/supervisord.conf`)

```ini
[supervisord]
nodaemon=true
user=wine
logfile=/dev/null
logfile_maxbytes=0

[program:xvfb]
command=Xvfb :1 -screen 0 1024x768x16
priority=1
autorestart=true
stdout_logfile=/dev/stdout
stdout_logfile_maxbytes=0
stderr_logfile=/dev/stderr
stderr_logfile_maxbytes=0

[program:x11vnc]
command=x11vnc -display :1 -nopw -forever -shared
priority=2
autorestart=true
stdout_logfile=/dev/stdout
stdout_logfile_maxbytes=0
stderr_logfile=/dev/stderr
stderr_logfile_maxbytes=0

[program:wine]
command=wine notepad
priority=3
autorestart=true
environment=DISPLAY=":1",WINEPREFIX="/home/wine/.wine",WINEARCH="win64"
stdout_logfile=/dev/stdout
stdout_logfile_maxbytes=0
stderr_logfile=/dev/stderr
stderr_logfile_maxbytes=0
```

---

### Step 5: VNC remote access

To visually interact with the Wine GUI from outside the container, we attach `x11vnc` to the existing Xvfb virtual display. This mirrors the framebuffer that Wine is already rendering to, without requiring a second display server.

- `x11vnc`: Lightweight VNC server that attaches to an existing X display.

Add `x11vnc` to the dependency installation in Step 2 and expose the VNC port:

```dockerfile
# Added to the Step 2 apk add command:
#   x11vnc

EXPOSE 5900
```

#### Connecting to the Container

Run the container with port mapping:

```bash
docker run --rm -p 5900:5900 savisor-node
```

Connect any VNC client (e.g., RealVNC, TigerVNC Viewer, Remmina) to `localhost:5900`.

### Step 6: Portable MetaTrader 5

Instead of installing MetaTrader 5 inside the container (which requires interactive setup, credential entry, and broker authentication), we use a **portable installation** created on a Windows machine. This pre-configured folder contains all account credentials, broker connections, Expert Advisors, and settings — ready to run without any manual provisioning.

#### Creating the Portable MetaTrader 5 Instance

On a **Windows 10 64-bit** machine:

1. Download the MetaTrader 5 installer from the official MQL5 website.
2. Run the installer and change the installation path to `C:\MetaTrader5`.
3. Launch MetaTrader 5, log into your broker account, configure your charts, indicators, and Expert Advisors.
4. Close MetaTrader 5 completely (including the system tray icon).
5. Create a file named `portable` (no extension) in the `C:\MetaTrader5` root directory. This tells MT5 to store all data (profiles, logs, configs) within the installation folder itself instead of `%APPDATA%`.
6. Launch MetaTrader 5 again to verify it runs in portable mode — all data files should now appear inside `C:\MetaTrader5`.
7. Close MetaTrader 5 and copy the entire `C:\MetaTrader5` folder to the root of this project as `MetaTrader5/`.

The resulting project structure:

```
savisor-node/
├── Dockerfile
├── README.md
├── supervisord/
│   └── supervisord.conf
└── MetaTrader5/
    ├── terminal64.exe
    ├── portable
    ├── MQL5/
    ├── config/
    ├── logs/
    └── ...
```

#### Dockerfile Integration

The portable folder is copied directly into the Wine C: drive during the build:

```dockerfile
COPY --chown=wine:wine MetaTrader5/ /home/wine/.wine/drive_c/MetaTrader5/
```

The supervisord `[program:wine]` section launches the terminal in portable mode:

```ini
[program:wine]
command=wine C:\MetaTrader5\terminal64.exe /portable
```

---

### Accumulative Dockerfile (Final)

```dockerfile
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
```
