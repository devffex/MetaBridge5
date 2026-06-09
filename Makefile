.PHONY: build-base build-gateway build-pipeline build-bot build-all run-gateway run-pipeline run-bot

# ==============================================================================
# Docker Build Orchestration Targets
# ==============================================================================

# 1. Build the shared Wine + MT5 + Python base image
build-base:
	docker build -f docker/Dockerfile.base -t savisor-base:latest .
	docker tag savisor-base:latest savisor-gateway:latest

# 2. Build the standalone Historical Data Ingest Pipeline container
build-pipeline:
	docker build -f apps/data-pipeline/Dockerfile -t savisor-pipeline:latest .

# 3. Build the standalone Algorithmic Trading Bot container
build-bot:
	docker build -f apps/trading-bot/Dockerfile -t savisor-bot:latest .

# 4. Build the standalone Chart Analysis Gateway container
build-chart-gateway:
	docker build -f apps/chart-gateway/Dockerfile -t savisor-chart-gateway:latest .

# 5. Build all targets sequentially
build-all: build-base build-pipeline build-bot build-chart-gateway

# ==============================================================================
# Standalone Container Running Targets (Local Testing)
# ==============================================================================

# Run the API Gateway locally with API port 8000 and VNC port 5900 exposed
run-gateway:
	docker run -it --rm \
		--name savisor-gateway-run \
		-p 8000:8000 \
		-p 5900:5900 \
		-e SAVISOR_API_KEY="test-api-key" \
		-e VNC_PASSWORD="test-vnc-password" \
		savisor-gateway:latest

# Run the Data Pipeline locally (will execute, print retrieved bars, and terminate)
run-pipeline:
	docker run -it --rm \
		--name savisor-pipeline-run \
		-e SAVISOR_API_KEY="test-api-key" \
		-e VNC_PASSWORD="test-vnc-password" \
		savisor-pipeline:latest

# Run the Trading Bot locally (will run for 15 price ticks and terminate)
run-bot:
	docker run -it --rm \
		--name savisor-bot-run \
		-e SAVISOR_API_KEY="test-api-key" \
		-e VNC_PASSWORD="test-vnc-password" \
		savisor-bot:latest

# Run the Chart Gateway locally with API port 8000 and VNC port 5900 exposed
run-chart-gateway:
	docker run -it --rm \
		--name savisor-chart-gateway-run \
		-p 8000:8000 \
		-p 5900:5900 \
		-e SAVISOR_API_KEY="test-api-key" \
		-e VNC_PASSWORD="test-vnc-password" \
		savisor-chart-gateway:latest
