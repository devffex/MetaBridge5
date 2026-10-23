# Base Image & Dependency Optimization Report

This report analyzes the base Docker image and the packages provisioned during the building process for `metabridge5-node`. It outlines concrete optimization strategies to reduce the final image footprint, specifically focusing on system libraries, Python packages, and Docker layer structures (excluding Wine and MetaTrader 5).

---

## Executive Summary

The base Docker image (`metabridge5-base:latest`) currently occupies **1.46 GB** of disk space. Excluding the MetaTrader 5 directory (~415 MB in the unoptimized container) and the Wine system folders (~208 MB), the base operating system, system utilities, and Python environment occupy **~853 MB**.

By addressing Docker layering inefficiency, pruning unnecessary Python testing suites, eliminating build-only dependencies, and replacing the Python-dependent system supervisor with a compiled alternative, we can reduce the base footprint by **~207.6 MB** (a **24.2% reduction** in the base image components size).

| Metric Component | Current Size | Optimized Size | Size Saved | Optimization Method |
| :--- | :---: | :---: | :---: | :--- |
| **System Packages (apk)** | 580.0 MB | 535.0 MB | **-45.0 MB** | Remove `curl`, `unzip`, `supervisor`, Linux `python3` |
| **Go Supervisord Binary** | 0.0 MB | 8.5 MB | **+8.5 MB** | Compile lightweight supervisor in Go stage |
| **Wheels Layer Bloat** | 33.2 MB | 0.0 MB | **-33.2 MB** | Use Docker BuildKit Bind Mounts during build |
| **Python Libraries** | 198.5 MB | 69.1 MB | **-129.4 MB** | Prune `tests`, `__pycache__`, uninstall build-only packages |
| **Total Base Components** | **853.0 MB** | **645.4 MB** | **-207.6 MB (-24.2%)** | Combined software and build optimizations |

---

## Docker Layer & Build Optimization Strategies

### 1. Eliminate Layer Bloat with BuildKit Bind Mounts
In [docker/Dockerfile.base](file://docker/Dockerfile.base#L120), the pre-downloaded wheels are copied using a `COPY` instruction, then installed via `pip install`, and subsequently deleted using `rm -rf`. 
* **The Problem**: Docker layers are additive. Once the `COPY` instruction commits the wheels to a layer history, deleting them in a subsequent `RUN` instruction only hides them from the final container. The ~33.2 MB footprint remains permanently in the image history.
* **The Solution**: Use a BuildKit bind mount during package installation. This exposes the wheels folder read-only from the builder stage only during the execution of that specific `RUN` command:
  ```dockerfile
  RUN --mount=type=bind,from=python-builder,source=/tmp/wheels,target=/home/wine/.wine/drive_c/wheels \
      wine C:\\python\\python.exe -m pip install --no-cache-dir --no-index --find-links C:\\wheels ...
  ```

### 2. Consolidate Setup and Setup-Time Pruning into a Single Layer
Currently, packages are installed, certificates are imported, and gRPC codegen is run across multiple separate `RUN` layers.
* **The Problem**: Each intermediate command modifies the file system, locking in unpruned configurations and temporary files.
* **The Solution**: Copy the base python runtime, certificate scripts, and codegen daemon, then execute the installation, cert imports, gRPC compilation, and file pruning inside a single `RUN` command. This ensures intermediate files are never written to the final image history.

---

## Library & Package Optimization Strategies

### 3. Prune Python Library Testing Suites & Bytecode Caches
Large Python dependencies (such as `pandas` and `numpy`) ship with massive unit testing packages and compiled bytecode caches (`__pycache__`) that are never imported at runtime.
* **Pruning Unit Tests**: Inside `/home/wine/.wine/drive_c/python/Lib/site-packages/`, the `pandas/tests/` folder alone occupies **38.3 MB**, and numpy test suites occupy **~17.7 MB**. Deleting directories named `test` or `tests` recursively saves **~56.0 MB**.
* **Pruning Bytecode**: The compiled `.pyc` files in `__pycache__` folders across the python runtime occupy **55.4 MB**. Deleting these recursively saves this space. To prevent the container from generating them at runtime, we set the environment variable:
  ```dockerfile
  ENV PYTHONDONTWRITEBYTECODE=1
  ```

### 4. Remove Build-Only Python Packages at Runtime
* **`grpcio-tools`**: Used solely to compile `terminal.proto` into Python classes. The compiled stubs only require the runtime `protobuf` and `grpcio` packages. Uninstalling `grpcio-tools` after codegen saves **2.6 MB**.
* **`pip`, `setuptools`, `wheel`**: Once python packages are successfully installed offline, these bootstrap utilities are redundant. Removing them saves **15.5 MB**.

### 5. Replace Python-Based System Supervisor
Alpine installs `supervisor` via `apk add supervisor`. This package depends on Linux `python3` (which is separate from the Windows Python environment running under Wine) and `py3-setuptools`.
* **The Problem**: Installing a second Python runtime (Linux) just to manage process startup is highly inefficient, adding **~45 MB** of system bloat.
* **The Solution**: Compile a lightweight process manager written in Go (such as the Go port of `supervisord`) in an intermediate build stage and copy the static binary directly. This maintains identical XML-RPC and `.conf` capabilities without requiring a Linux Python installation.

---

## Actionable Optimized Dockerfile

Below is the proposed, fully optimized [docker/Dockerfile.base](file://docker/Dockerfile.base) structure incorporating all identified strategies:

```dockerfile
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
    grpcio grpcio-tools protobuf numpy pandas MetaTrader5 pip setuptools wheel tzdata pytz colorama

# 4. Bootstrap pip, setuptools, and wheel offline by unzipping their wheels into site-packages
RUN unzip -o /tmp/wheels/pip-*.whl -d /tmp/python/Lib/site-packages/ && \
    unzip -o /tmp/wheels/setuptools-*.whl -d /tmp/python/Lib/site-packages/ && \
    unzip -o /tmp/wheels/wheel-*.whl -d /tmp/python/Lib/site-packages/

# ==========================================
# STAGE 3: Go Supervisor Builder
# ==========================================
FROM golang:alpine AS supervisor-builder
RUN apk add --no-cache git && \
    git clone https://github.com/ochinchina/supervisord.git /src && \
    cd /src && \
    CGO_ENABLED=0 go build -ldflags "-s -w" -o /go/bin/supervisord

# ==========================================
# STAGE 4: Final Runtime Base Image
# ==========================================
FROM alpine:latest

# Combine apk packages to reduce layer overhead (Removed curl, unzip, supervisor, python3)
RUN apk add --no-cache --repository http://dl-cdn.alpinelinux.org/alpine/edge/community \
    bash \
    xvfb \
    freetype \
    fontconfig \
    x11vnc \
    wine \
    gnutls \
    ca-certificates \
    tzdata \
    xdotool \
    libfaketime && \
    rm -rf /usr/lib/wine/i386-windows

# Copy the compiled Go supervisord binary
COPY --from=supervisor-builder /go/bin/supervisord /usr/bin/supervisord

# Set up user and environment variables for Wine
ENV WINEPREFIX=/home/wine/.wine
ENV WINEARCH=win64
ENV DISPLAY=:1
ENV WINEDLLOVERRIDES="mscoree=disabled"
# Prevent Python from writing bytecode at runtime
ENV PYTHONDONTWRITEBYTECODE=1

# Create wine user and workspace
RUN adduser -D -u 1000 wine && \
    mkdir -p /home/wine/.wine && \
    chown -R wine:wine /home/wine

# Copy the compiled Microsoft fonts from Stage 1
COPY --from=font-builder /usr/share/fonts/truetype/msttcorefonts/ /usr/share/fonts/truetype/msttcorefonts/

# Rebuild font cache
RUN fc-cache -f

# Copy supervisord configuration and helper scripts
COPY docker/supervisord.conf /etc/supervisord.conf
COPY --chown=wine:wine docker/supervisord/dismiss_dialogs.sh /home/wine/dismiss_dialogs.sh
COPY --chown=wine:wine docker/supervisord/startup_guard.sh /home/wine/startup_guard.sh
COPY --chown=wine:wine docker/supervisord/vnc_passwd_setup.sh /home/wine/vnc_passwd_setup.sh
COPY --chown=wine:wine docker/supervisord/entrypoint.sh /home/wine/entrypoint.sh
COPY --chown=wine:wine docker/daemon/ /home/wine/.wine/drive_c/daemon/
RUN chmod +x /home/wine/dismiss_dialogs.sh /home/wine/startup_guard.sh /home/wine/vnc_passwd_setup.sh /home/wine/entrypoint.sh

# Copy portable MetaTrader 5 from host
COPY --chown=wine:wine MetaTrader5/ /home/wine/.wine/drive_c/MetaTrader5/

# Configure system timezone name for Wine's timezone auto-detection
RUN echo "UTC" > /etc/timezone

# Clean up any pre-baked host-specific terminal license and account cache
RUN rm -f /home/wine/.wine/drive_c/MetaTrader5/Config/terminal.lic \
          /home/wine/.wine/drive_c/MetaTrader5/Config/accounts.dat

# Perform setup tasks as the wine user
USER wine
WORKDIR /home/wine

# Create the VNC password directory
RUN mkdir -p /home/wine/.vnc

# Copy the prepared Windows Python base from Stage 2
COPY --chown=wine:wine --from=python-builder /tmp/python/ /home/wine/.wine/drive_c/python/

# Copy certificate importer script
COPY --chown=wine:wine docker/import_certs.py /home/wine/.wine/drive_c/import_certs.py

# Single command layer: Init Wine, Install packages, run config/codegen, prune all bloating files
RUN --mount=type=bind,from=python-builder,source=/tmp/wheels,target=/home/wine/.wine/drive_c/wheels \
    wineboot --init && \
    wine reg add "HKLM\\Software\\Microsoft\\Cryptography\\Defaults\\Provider Types\\Type 024" /v Name /t REG_SZ /d "Microsoft Enhanced RSA and AES Cryptographic Provider" /f && \
    wine reg add "HKLM\\Software\\Microsoft\\Cryptography\\Defaults\\Provider Types\\Type 024" /v TypeName /t REG_SZ /d "RSA Full and AES" /f && \
    wine reg add "HKLM\\Software\\Microsoft\\Cryptography\\Defaults\\Provider\\Microsoft Enhanced RSA and AES Cryptographic Provider" /v "Image Path" /t REG_SZ /d "rsaenh.dll" /f && \
    wine reg add "HKLM\\Software\\Microsoft\\Cryptography\\Defaults\\Provider\\Microsoft Enhanced RSA and AES Cryptographic Provider" /v Type /t REG_DWORD /d 24 /f && \
    wine reg add "HKLM\\Software\\Microsoft\\Cryptography\\Defaults\\Provider\\Microsoft Enhanced RSA and AES Cryptographic Provider" /v SigInFile /t REG_DWORD /d 0 /f && \
    # Install Python libraries offline using the bind mount
    wine C:\\python\\python.exe -m pip install --no-cache-dir --no-index --find-links C:\\wheels \
        grpcio grpcio-tools protobuf numpy pandas MetaTrader5 tzdata pytz colorama && \
    # Import root certs into Wine
    wine C:\\python\\python.exe C:\\import_certs.py && \
    rm -f /home/wine/.wine/drive_c/import_certs.py && \
    # Run codegen
    wine C:\\python\\python.exe C:\\daemon\\codegen.py && \
    # Uninstall build-only tools
    wine C:\\python\\python.exe -m pip uninstall -y grpcio-tools && \
    # Remove Pip/Setuptools/Wheel files
    rm -rf /home/wine/.wine/drive_c/python/Lib/site-packages/pip* \
           /home/wine/.wine/drive_c/python/Lib/site-packages/setuptools* \
           /home/wine/.wine/drive_c/python/Lib/site-packages/wheel* && \
    # Remove test folders recursively
    find /home/wine/.wine/drive_c/python/Lib/site-packages -type d \( -name "test" -o -name "tests" \) -exec rm -rf {} + && \
    # Remove pycache recursively
    find /home/wine/.wine/drive_c/python -type d -name "__pycache__" -exec rm -rf {} + && \
    # Shutdown wineserver to persist registry writes
    wineserver -w

EXPOSE 5900 50051

ENTRYPOINT ["/usr/bin/supervisord", "-c", "/etc/supervisord.conf"]
```

---

## Verification Plan

To verify that these optimizations do not alter runtime behavior:

### Automated/Local Executable Verification
* **Build Base Image**:
  ```bash
  docker build -f docker/Dockerfile.base -t metabridge5-base:optimized .
  ```
* **Verify System Services Sequence**:
  Run `run-gateway` from the Makefile to start Supervisord. Verify that:
  - `xvfb` and `x11vnc` start successfully.
  - Wine boots and runs `terminal64.exe` correctly.
  - The gRPC server initializes on port `50051` inside Wine Python.
* **Test Application Functions**:
  Run a test request via a python gRPC client to query market data ticks or accounts to confirm communication with the terminal behaves identically.
