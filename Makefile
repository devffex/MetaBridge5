.PHONY: build-core build-gateway build-analytics build-backup build-all size-check test up down clean build-base build-market-node build-node run-market-node run-node run-base

# ==============================================================================
# Docker Build Orchestration Targets (Microservice Architecture)
# ==============================================================================

# 1. Build metabridge5-core (Headless Wine + MT5 + gRPC server)
build-core:
	docker build -f docker/Dockerfile.core -t metabridge5-core:latest .

# 2. Build metabridge5-market-gateway (FastAPI + WebSocket + Parquet exporter)
build-gateway:
	docker build -f apps/market-gateway/Dockerfile -t metabridge5-market-gateway:latest apps/market-gateway

# 3. Build metabridge5-duckdb-analytics (DuckDB Vectorized Query Engine)
build-analytics:
	docker build -f apps/duckdb-analytics/Dockerfile -t metabridge5-duckdb-analytics:latest apps/duckdb-analytics

# 4. Build metabridge5-backup-sync (Autonomous rclone backup and restore daemon)
build-backup:
	docker build -f apps/backup-sync/Dockerfile -t metabridge5-backup-sync:latest apps/backup-sync

# 5. Build all microservice images
build-all: build-core build-gateway build-analytics build-backup

# 6. Verify image sizes against strict optimization budgets
size-check:
	bash scripts/check_image_sizes.sh

# 7. Run local test suite
test:
	apps/market-gateway/.venv/bin/pytest apps/market-gateway/tests
	apps/duckdb-analytics/.venv/bin/pytest apps/duckdb-analytics/tests

# 8. Start full container topology via Docker Compose
up:
	docker compose up -d

# 9. Stop full container topology
down:
	docker compose down

# ==============================================================================
# Legacy Monolithic Image Targets (Maintained for Backward Compatibility)
# ==============================================================================

build-base:
	docker build -f docker/Dockerfile.base -t metabridge5-base:latest .

build-market-node: build-base
	docker build -f apps/market-gateway/Dockerfile -t metabridge5-market-node:latest .

build-node: build-market-node

run-market-node:
	docker run -it --rm \
		--name metabridge5-market-node-run \
		--stop-timeout 45 \
		-p 8000:8000 \
		-p 127.0.0.1:5900:5900 \
		-e START_VNC="true" \
		-e METABRIDGE5_API_KEY="test-api-key" \
		-e VNC_PASSWORD="test-vnc-password" \
		-e STORAGE_BACKEND="local" \
		-e AUDIT_LOG_SINK="sqlite" \
		metabridge5-market-node:latest

run-node: run-market-node

run-base:
	docker run -it --rm \
		--name metabridge5-base-run \
		--stop-timeout 45 \
		-p 50051:50051 \
		-p 127.0.0.1:5900:5900 \
		-e START_VNC="true" \
		-e VNC_PASSWORD="test-vnc-password" \
		metabridge5-base:latest

# ==============================================================================
# Cleanup Targets
# ==============================================================================
clean:
	-docker rm -f metabridge5-market-node-run metabridge5-base-run metabridge5-core metabridge5-market-gateway metabridge5-duckdb-analytics metabridge5-backup-sync 2>/dev/null || true
