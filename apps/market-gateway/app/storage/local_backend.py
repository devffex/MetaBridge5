import logging
import os
from pathlib import Path

from app.storage.base import StorageBackend

logger = logging.getLogger("storage.local")


class LocalStorageBackend(StorageBackend):
    """
    Local filesystem storage backend.
    Used for local development, testing, and container disk staging.
    """

    def __init__(self, base_dir: str | None = None, base_url: str = "http://localhost:8000/static"):
        resolved_dir = base_dir or os.environ.get("METABRIDGE5_DATA_DIR", "/tmp/metabridge5_data")
        self.base_dir = Path(resolved_dir)
        self.base_url = base_url.rstrip("/")
        self.base_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"Initialized LocalStorageBackend at {self.base_dir}")

    def upload_file(
        self,
        local_path: str,
        remote_path: str,
        content_type: str = "application/octet-stream",
        metadata: dict[str, str] | None = None,
    ) -> bool:
        try:
            target_path = self.base_dir / remote_path.lstrip("/")
            target_path.parent.mkdir(parents=True, exist_ok=True)
            with open(local_path, "rb") as src, open(target_path, "wb") as dst:
                dst.write(src.read())
            logger.info(f"Saved file locally: {target_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to save local file {remote_path}: {e}")
            return False

    def upload_bytes(
        self,
        data: bytes,
        remote_path: str,
        content_type: str = "application/octet-stream",
        metadata: dict[str, str] | None = None,
    ) -> bool:
        try:
            target_path = self.base_dir / remote_path.lstrip("/")
            target_path.parent.mkdir(parents=True, exist_ok=True)
            target_path.write_bytes(data)
            logger.debug(f"Wrote {len(data)} bytes to {target_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to write bytes to {remote_path}: {e}")
            return False

    def get_public_url(self, remote_path: str) -> str:
        clean_path = remote_path.lstrip("/")
        return f"{self.base_url}/{clean_path}"

    def check_exists(self, remote_path: str) -> bool:
        target_path = self.base_dir / remote_path.lstrip("/")
        return target_path.exists()

    def read_bytes(self, remote_path: str) -> bytes | None:
        target_path = self.base_dir / remote_path.lstrip("/")
        if target_path.exists():
            return target_path.read_bytes()
        return None
