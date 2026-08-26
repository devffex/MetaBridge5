from abc import ABC, abstractmethod


class StorageBackend(ABC):
    """
    Abstract Base Class defining the storage strategy interface.
    Enables pluggable destinations for historical datasets (GitHub Public Repo, S3/R2, Local).
    """

    @abstractmethod
    def upload_file(
        self,
        local_path: str,
        remote_path: str,
        content_type: str = "application/octet-stream",
        metadata: dict[str, str] | None = None,
    ) -> bool:
        """Uploads a local file to the storage destination."""

    @abstractmethod
    def upload_bytes(
        self,
        data: bytes,
        remote_path: str,
        content_type: str = "application/octet-stream",
        metadata: dict[str, str] | None = None,
    ) -> bool:
        """Uploads raw bytes directly to the storage destination."""

    @abstractmethod
    def get_public_url(self, remote_path: str) -> str:
        """Returns the public CDN / direct URL for the remote object."""

    @abstractmethod
    def check_exists(self, remote_path: str) -> bool:
        """Checks if a file exists at the remote path."""

    @abstractmethod
    def read_bytes(self, remote_path: str) -> bytes | None:
        """Reads and returns the bytes of a remote file if it exists."""
