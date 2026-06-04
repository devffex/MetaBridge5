# API Wrapper

This directory contains the FastAPI-based REST API wrapper that exposes MetaTrader 5 terminal operations over HTTP.

## Technical Architecture

The wrapper executes within the Wine environment inside the container, utilizing Wine's Python interpreter to interface with the native MetaTrader 5 library via a Named Pipe connection.

**Request Routing**
Requests arrive at FastAPI, which validates credentials using `api/auth.py`. Route handlers convert request payloads into the parameters required by the `MetaTrader5` library.

**Thread Pool Execution**
Because the `MetaTrader5` library performs blocking network requests and Named Pipe I/O, route handlers execute calls inside a separate thread pool using `asyncio.to_thread`. This design maintains the responsiveness of the async FastAPI event loop.

**Mock Fallback**
When executed outside the Wine container (e.g. during local developer testing), the native `MetaTrader5` library is unavailable. The code automatically imports the `tests/mock_mt5.py` wrapper, allowing off-container development, linting, and unit testing.

## Local Configuration

To run and test the API locally, set up a virtual environment and run testing/linting tools.

**Virtual Environment Setup**
```bash
uv venv
source .venv/bin/activate
uv pip install -r pyproject.toml
```

**Code Formatting**
```bash
uv run ruff format
```

**Linter and Type Checks**
```bash
uv run ruff check
```

**Unit Tests**
```bash
uv run pytest
```
