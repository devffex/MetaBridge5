import logging
import os
from typing import ClassVar

from app.storage.base import StorageBackend
from app.storage.github_backend import GitHubStorageBackend
from app.storage.local_backend import LocalStorageBackend
from app.storage.s3_backend import S3StorageBackend

logger = logging.getLogger("storage.factory")


class StorageFactory:
    """
    Factory to resolve and instantiate the active storage backend.
    """

    _cached_instances: ClassVar[dict[str, StorageBackend]] = {}

    @classmethod
    def get_backend(cls, backend_type: str | None = None, **kwargs) -> StorageBackend:
        selected = (backend_type or os.environ.get("STORAGE_BACKEND", "local")).lower().strip()

        if selected in cls._cached_instances and not kwargs:
            return cls._cached_instances[selected]

        backend: StorageBackend
        if selected == "github":
            backend = GitHubStorageBackend(**kwargs)
        elif selected in ("s3", "r2", "minio"):
            backend = S3StorageBackend(**kwargs)
        elif selected == "local":
            backend = LocalStorageBackend(**kwargs)
        else:
            logger.warning(f"Unknown STORAGE_BACKEND '{selected}'. Falling back to 'local'.")
            backend = LocalStorageBackend(**kwargs)

        if not kwargs:
            cls._cached_instances[selected] = backend

        return backend

    @classmethod
    def reset_cache(cls):
        """Clears cached singleton instances (useful for testing)."""
        cls._cached_instances.clear()
