# Savisor Node

Reprenset an light weight and isolated metatrader terminal running under wine in a docker linux container. Which expose different interfaces to interact with the terminal with different protocols and process.

## Image Builder

### Insider Image Builder

To build the Savisor Node container, we use Alpine Linux as the lightweight base image, compiling a headless MetaTrader 5 installation with Wine support.

To pull the base Alpine Linux image, run:

```bash
docker pull alpine:latest
```

#### Why Building from Scratch is the Optimal Path

Building the Docker image from scratch using Alpine Linux is the most reliable approach for several key reasons:

- **Minimal Footprint**: Alpine Linux's base image size is only 5MB. Even after installing Wine and MetaTrader 5, the container remains exceptionally lightweight compared to bloated Debian/Ubuntu-based Wine alternatives.
- **Security & Attack Surface Reduction**: Trading terminals manage real financial capital. Running a bare-minimum Alpine environment eliminates unnecessary system utilities, packages, and services, significantly minimizing the potential security vulnerabilities.
- **Resource Optimization**: Automated trading requires high stability and minimal latency. By stripping out graphical desktop environments, audio servers (PulseAudio), and display components (X11), the container consumes very little CPU and memory. This allows running multiple concurrent, isolated terminal nodes on a single host.
- **Absolute Version Control**: Pre-built Wine containers frequently introduce automatic, breaking updates. Building from scratch ensures that the exact versions of Wine, Mono, and MetaTrader 5 are pinned, providing deterministic, reproducible environments.
