import base64
import logging
import os
import time

import httpx

from app.storage.base import StorageBackend

logger = logging.getLogger("storage.github")


class GitHubStorageBackend(StorageBackend):
    """
    GitHub Public Repository storage backend.
    Enables free global dataset hosting using GitHub as a versioned storage sink,
    distributed through raw.githubusercontent.com or Cloudflare CDN.
    """

    def __init__(
        self,
        token: str | None = None,
        repo: str | None = None,
        branch: str = "main",
        cdn_base_url: str | None = None,
        enable_jsdelivr_purge: bool = True,
    ):
        self.token = token or os.environ.get("GITHUB_TOKEN", "")
        self.repo = repo or os.environ.get("GITHUB_REPO", "")
        self.branch = branch or os.environ.get("GITHUB_BRANCH", "main")
        self.cdn_base_url = cdn_base_url or os.environ.get("GITHUB_CDN_BASE_URL", "")
        self.enable_jsdelivr_purge = enable_jsdelivr_purge

        if not self.cdn_base_url and self.repo:
            # Default to jsDelivr Multi-CDN (Cloudflare + Fastly edge servers) for public repos
            self.cdn_base_url = f"https://cdn.jsdelivr.net/gh/{self.repo}@{self.branch}"

        self.api_base = f"https://api.github.com/repos/{self.repo}"
        self.headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if self.token:
            self.headers["Authorization"] = f"Bearer {self.token}"

        logger.info(
            f"Initialized GitHubStorageBackend for repo '{self.repo}' branch '{self.branch}' (CDN: {self.cdn_base_url})"
        )

    def _get_file_sha(self, remote_path: str) -> str | None:
        """Fetches the current blob SHA of an existing file in GitHub."""
        clean_path = remote_path.lstrip("/")
        url = f"{self.api_base}/contents/{clean_path}?ref={self.branch}"
        try:
            with httpx.Client(timeout=10.0) as client:
                res = client.get(url, headers=self.headers)
                if res.status_code == 200:
                    return res.json().get("sha")
                elif res.status_code == 404:
                    return None
                else:
                    logger.warning(f"GitHub SHA lookup returned {res.status_code}: {res.text}")
                    return None
        except Exception as e:
            logger.error(f"Error fetching GitHub file SHA for {remote_path}: {e}")
            return None

    def upload_bytes(
        self,
        data: bytes,
        remote_path: str,
        content_type: str = "application/octet-stream",
        metadata: dict[str, str] | None = None,
    ) -> bool:
        clean_path = remote_path.lstrip("/")
        url = f"{self.api_base}/contents/{clean_path}"
        sha = self._get_file_sha(clean_path)
        content_b64 = base64.b64encode(data).decode("utf-8")

        commit_message = f"chore(data): sync {clean_path} [{int(time.time())}]"
        payload = {
            "message": commit_message,
            "content": content_b64,
            "branch": self.branch,
        }
        if sha:
            payload["sha"] = sha

        try:
            with httpx.Client(timeout=30.0) as client:
                res = client.put(url, headers=self.headers, json=payload)
                if res.status_code in (200, 201):
                    logger.info(f"Successfully committed {clean_path} to GitHub ({len(data)} bytes)")
                    if self.enable_jsdelivr_purge and "jsdelivr.net" in self.cdn_base_url:
                        self._purge_jsdelivr_cache(clean_path)
                    return True
                else:
                    logger.error(f"Failed to commit to GitHub: {res.status_code} - {res.text}")
                    return False
        except Exception as e:
            logger.error(f"Exception during GitHub upload_bytes for {clean_path}: {e}")
            return False

    def _purge_jsdelivr_cache(self, clean_path: str):
        """Triggers jsDelivr instant cache invalidation API."""
        purge_url = f"https://purge.jsdelivr.net/gh/{self.repo}@{self.branch}/{clean_path}"
        try:
            with httpx.Client(timeout=5.0) as client:
                res = client.get(purge_url)
                if res.status_code == 200:
                    logger.debug(f"Purged jsDelivr cache for {clean_path}")
                else:
                    logger.warning(f"jsDelivr cache purge returned {res.status_code} for {clean_path}")
        except Exception as e:
            logger.warning(f"Could not purge jsDelivr cache for {clean_path}: {e}")

    def upload_file(
        self,
        local_path: str,
        remote_path: str,
        content_type: str = "application/octet-stream",
        metadata: dict[str, str] | None = None,
    ) -> bool:
        try:
            with open(local_path, "rb") as f:
                data = f.read()
            return self.upload_bytes(data, remote_path, content_type, metadata)
        except Exception as e:
            logger.error(f"Failed to read local file {local_path} for GitHub upload: {e}")
            return False

    def get_public_url(self, remote_path: str) -> str:
        clean_path = remote_path.lstrip("/")
        if self.cdn_base_url:
            return f"{self.cdn_base_url.rstrip('/')}/{clean_path}"
        return f"https://raw.githubusercontent.com/{self.repo}/{self.branch}/{clean_path}"

    def check_exists(self, remote_path: str) -> bool:
        return self._get_file_sha(remote_path) is not None

    def read_bytes(self, remote_path: str) -> bytes | None:
        url = self.get_public_url(remote_path)
        try:
            with httpx.Client(timeout=15.0) as client:
                res = client.get(url, headers=self.headers)
                if res.status_code == 200:
                    return res.content
                return None
        except Exception as e:
            logger.error(f"Failed to read remote file {url}: {e}")
            return None
