# Runtime Bottlenecks & Production Optimizations

This pull request resolves runtime bottlenecks and applies production hardening across the MetaBridge5 container stack.
The runtime builds on Alpine 3.20, Wine 64-bit, and supervisord.
It isolates MetaTrader 5 inside a minimal container and exposes a thread-safe gRPC bridge daemon on port 50051.
The Tier 2 market gateway runs FastAPI and WebSocket services.

The changes address 5 operational bottlenecks and 5 production optimizations.
Each item was implemented in an atomic commit on the feature branch.

## Changes by Domain

### Native Build & Wheel Extraction

#### Extract Windows AMD64 Wheels Natively
Unpacks Windows Python wheels directly on Linux during the multi-stage Docker build. This eliminates running emulated Windows Python inside Wine during image generation, cutting image build time and image size.

#### Harden Version Pinning for Dependencies
Pins `GRPC_VERSION`, `PROTOBUF_VERSION`, `NUMPY_VERSION`, and `PSUTIL_VERSION` across both builder stages and runtime packages. This prevents ABI drift between generated protobuf stubs and runtime libraries.

#### Prune Build Tools from Final Image
Restricts copied files to `grpc_server.py` and pre-generated stubs. Strips code generation scripts, proto sources, test clients, and package managers from the final runtime image.

### Storage Isolation & Volume Persistence

#### Isolate Application Binaries to Dedicated Directory
Moves MetaTrader 5 binaries to `/opt/metabridge5/MetaTrader5/`. Sets ownership to root and marks binaries read-only. Locks `liveupdate/` to prevent auto-updates inside containers.

#### Seed Wine Prefix for Sub-Second Cold Boots
Pre-initializes the Wine prefix during image build into `/opt/wine-seed`. Deploys the seed into empty runtime volumes in sub-second time on container boot.

#### Redirect Mutable MT5 Data to Persistent Volume
Symlinks mutable folders (`Config`, `Bases`, `MQL5`, `Profiles`, `logs`, `Tester`) to `/home/wine/.wine/drive_c/mt5-data/`. This preserves user accounts, charts, and trading logs across image upgrades.

### Process Management & Graceful Shutdown

#### Wire Tini as Init Process PID 1
Configures `/sbin/tini --` as the container entrypoint. Reaps zombie processes and forwards POSIX termination signals down the process hierarchy.

#### Orchestrate Graceful Terminal Shutdown
Replaces hard termination with `wine taskkill /IM terminal64.exe` to send standard `WM_CLOSE` messages. Allows terminal64.exe to cleanly flush open database transactions and chart states.

#### Conditional Wineserver Registry Flush
Flushes `wineserver -w` only on container shutdown when no other Wine processes run. Leaves wineserver active if `StopTerminal` RPC halts only the MT5 terminal.

#### Extend Container Stop Grace Periods
Increases container stop timeouts to 45 seconds across supervisord configuration, docker-compose, and Makefile run targets. Prevents Docker from killing Wine before disk writes complete.

### Display Architecture & Network Gating

#### Implement Conditional Headless Framebuffer
Configures virtual framebuffer geometry dynamically. Uses `800x600x16` in headless production mode to cut memory consumption while preserving 16-bit TrueColor depth required by Wine. Uses `1280x800x16` when VNC is enabled.

#### Gate Remote Desktop Server
Starts `x11vnc` only when `START_VNC=true`. Skips VNC server execution and password generation during automated headless operations, reducing idle CPU usage to 0%.

#### Loopback Isolation for VNC
Removes `-localhost` from container-level x11vnc execution.
Binds host port mapping strictly to loopback `127.0.0.1:5900:5900` in docker-compose and Makefile.
This prevents open exposure on external network interfaces.

### Base Distribution & Ownership Mapping

#### Pin Base Distribution Repositories
Eliminates floating Alpine edge repositories in favor of pinned Alpine 3.20 packages. Pins supervisord git repository to tag `v0.7.3` and pins `uv` to `0.4.30`.

#### Reconcile Volume Ownership on UID Mismatch
Inspects volume ownership against `PUID:PGID` via `stat -c %u:%g`. Skips expensive recursive `chown -R` scans when ownership already matches. Drops root privileges permanently using `su-exec` before starting supervisord.

## Verification Checklist

- [x] Verified shell scripts syntax via `bash -n docker/supervisord/*.sh`.
- [x] Ran full unit and integration test suite via `uv run pytest` (59 tests passed).
- [x] Verified Alpine 3.20 package availability for `msttcorefonts-installer`.
- [x] Tested graceful shutdown flow with `taskkill` and conditional wineserver flushing.
- [x] Verified VNC port loopback isolation in docker-compose.yml and Makefile.
