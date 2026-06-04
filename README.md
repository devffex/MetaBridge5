# Savisor Node

Savisor Node runs an isolated MetaTrader 5 terminal under Wine in a lightweight Alpine Linux Docker container. It exposes a secure FastAPI REST API to programmatically interact with MT5 and a password-protected VNC server for graphical administration.

## Features

- **Minimal Footprint**: Alpine-based multi-stage build.
- **Headless Execution**: Runs MT5 using X Virtual Framebuffer (`Xvfb`) in memory.
- **Secure REST API**: Fast API key authentication (`Authorization: Bearer <key>`) with timing attack protection.
- **Secure VNC Access**: Remote desktop mirroring via `x11vnc` with password authentication.
- **Startup Guard**: Container fails fast if required environment secrets are missing.
- **Supervisor Orchestration**: Gracefully handles restarts, sequence priority, and standard logging.

---

## Prerequisites & Installation

### 1. Set Up Portable MetaTrader 5

To run MT5 under Wine without manual setup inside the container, prepare a **portable installation** folder on a Windows 10/11 64-bit machine:

1. Download and run the MT5 installer. Set the installation path to `C:\MetaTrader5`.
2. Close the terminal completely.
3. Relaunch in portable mode from cmd/PowerShell:
   ```cmd
   C:\MetaTrader5\terminal64.exe /portable
   ```
4. Log into your broker account, set up broker servers, and configure charts/indicators.
5. Close MT5 and copy the entire `C:\MetaTrader5` folder to the root of this project as `MetaTrader5/`.

The project directory structure should look like this:
```text
savisor-node/
├── Dockerfile
├── README.md
├── supervisord/
│   └── supervisord.conf
└── MetaTrader5/
    ├── terminal64.exe
    ├── MQL5/
    └── ...
```

---

## Build and Run

### 1. Build the Docker Image
```bash
docker build -t savisor/savisor-node:latest .
```

### 2. Run the Container
Both the REST API and VNC require authentication secrets to start:

```bash
docker run -d \
  --name savisor-node \
  -p 8000:8000 \
  -p 5900:5900 \
  -e SAVISOR_API_KEY="your-secret-api-key" \
  -e VNC_PASSWORD="your-vnc-password" \
  savisor/savisor-node:latest
```

---

## Usage Guide

### 1. REST API
FastAPI exposes the REST interface on port `8000`.

- **Liveness Probe** (Unauthenticated):
  ```bash
  curl -i http://localhost:8000/health
  ```
- **Read Root** (Unauthenticated):
  ```bash
  curl -i http://localhost:8000/
  ```
- **Operational MT5 Endpoints** (Requires API Key):
  ```bash
  curl -i -X GET http://localhost:8000/api/v1/terminals/trade/account \
    -H "Authorization: Bearer your-secret-api-key"
  ```
  See `api/curl_tests.md` for a comprehensive list of curl examples.

### 2. GUI VNC Access
Connect to `localhost:5900` using any standard VNC client (TigerVNC, RealVNC, Remmina, etc.) and enter your `VNC_PASSWORD`.
> **Note**: The RFB VNC protocol truncates passwords to 8 characters max.

---

## Local Development & Testing

Python dependencies and virtual environments are managed using `uv` inside the `api` folder.

1. **Format Code**:
   ```bash
   uv run --project api ruff format
   ```
2. **Lint Code**:
   ```bash
   uv run --project api ruff check
   ```
3. **Run Unit Tests**:
   ```bash
   uv run --project api pytest
   ```

---

## Docker Hub Deployment

The image is pushed to the private Docker Hub repository:
`https://hub.docker.com/repository/docker/savisor/savisor-node`
```bash
docker tag savisor/savisor-node:latest savisor/savisor-node:latest
docker push savisor/savisor-node:latest
```
