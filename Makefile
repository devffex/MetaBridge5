.PHONY: build-base build-market-node build-node build-all run-market-node run-node run-base clean

# ==============================================================================
# Docker Build Orchestration Targets
# ==============================================================================

# 1. Build the foundational Tier 1 Wine + MT5 + gRPC base image
build-base:
	docker build -f docker/Dockerfile.base -t savisor-base:latest .

# 2. Build the autonomous Tier 2 Market Node container (FastAPI + WebSocket + Pipeline)
build-market-node:
	docker build -f apps/market-gateway/Dockerfile -t savisor-market-node:latest .

build-node: build-market-node

# 3. Build full stack sequentially
build-all: build-base build-market-node

# ==============================================================================
# Container Running Targets (Local Testing & Development)
# ==============================================================================

# Run the full Market Node locally with REST/WS on 8000 and VNC on 5900 exposed
run-market-node:
	docker run -it --rm \
		--name savisor-market-node-run \
		-p 8000:8000 \
		-p 5900:5900 \
		-e SAVISOR_API_KEY="test-api-key" \
		-e VNC_PASSWORD="test-vnc-password" \
		-e STORAGE_BACKEND="local" \
		-e AUDIT_LOG_SINK="sqlite" \
		savisor-market-node:latest

run-node: run-market-node

# Run the base infrastructure container standalone for headless MT5/VNC debugging
run-base:
	docker run -it --rm \
		--name savisor-base-run \
		-p 50051:50051 \
		-p 5900:5900 \
		-e VNC_PASSWORD="test-vnc-password" \
		savisor-base:latest

# ==============================================================================
# Cleanup Targets
# ==============================================================================
clean:
	-docker rm -f savisor-market-node-run savisor-base-run 2>/dev/null || true
