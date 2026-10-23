import io
import logging
import os

import boto3
from botocore.exceptions import ClientError

from app.storage.base import StorageBackend

logger = logging.getLogger("storage.s3")


class S3StorageBackend(StorageBackend):
    """
    S3 / Cloudflare R2 / MinIO compatible object storage backend.
    Optimized for zero-egress cloud delivery (Cloudflare R2) and S3 standard buckets.
    """

    def __init__(
        self,
        bucket_name: str | None = None,
        endpoint_url: str | None = None,
        access_key: str | None = None,
        secret_key: str | None = None,
        region_name: str | None = None,
        cdn_base_url: str | None = None,
    ):
        self.bucket_name = bucket_name or os.environ.get("S3_BUCKET_NAME", "metabridge5-market-data")
        self.endpoint_url = endpoint_url or os.environ.get("S3_ENDPOINT_URL")
        self.access_key = access_key or os.environ.get("S3_ACCESS_KEY_ID") or os.environ.get("AWS_ACCESS_KEY_ID")
        self.secret_key = (
            secret_key or os.environ.get("S3_SECRET_ACCESS_KEY") or os.environ.get("AWS_SECRET_ACCESS_KEY")
        )
        self.region_name = (
            region_name or os.environ.get("S3_REGION_NAME") or os.environ.get("AWS_DEFAULT_REGION", "auto")
        )
        self.cdn_base_url = cdn_base_url or os.environ.get("S3_CDN_BASE_URL")

        client_kwargs = {
            "region_name": self.region_name,
        }
        if self.endpoint_url:
            client_kwargs["endpoint_url"] = self.endpoint_url
        if self.access_key and self.secret_key:
            client_kwargs["aws_access_key_id"] = self.access_key
            client_kwargs["aws_secret_access_key"] = self.secret_key

        self.s3_client = boto3.client("s3", **client_kwargs)
        logger.info(f"Initialized S3StorageBackend for bucket '{self.bucket_name}' endpoint '{self.endpoint_url}'")

    def upload_file(
        self,
        local_path: str,
        remote_path: str,
        content_type: str = "application/octet-stream",
        metadata: dict[str, str] | None = None,
    ) -> bool:
        clean_path = remote_path.lstrip("/")
        extra_args: dict[str, str] = {
            "ContentType": content_type,
            "CacheControl": "public, max-age=60",
        }
        if metadata:
            extra_args["Metadata"] = metadata

        try:
            self.s3_client.upload_file(
                Filename=local_path,
                Bucket=self.bucket_name,
                Key=clean_path,
                ExtraArgs=extra_args,
            )
            logger.info(f"Uploaded file {local_path} to s3://{self.bucket_name}/{clean_path}")
            return True
        except ClientError as e:
            logger.error(f"S3 upload_file failed for {clean_path}: {e}")
            return False

    def upload_bytes(
        self,
        data: bytes,
        remote_path: str,
        content_type: str = "application/octet-stream",
        metadata: dict[str, str] | None = None,
    ) -> bool:
        clean_path = remote_path.lstrip("/")
        extra_args: dict[str, str] = {
            "ContentType": content_type,
            "CacheControl": "public, max-age=60",
        }
        if metadata:
            extra_args["Metadata"] = metadata

        try:
            fileobj = io.BytesIO(data)
            self.s3_client.upload_fileobj(
                Fileobj=fileobj,
                Bucket=self.bucket_name,
                Key=clean_path,
                ExtraArgs=extra_args,
            )
            logger.info(f"Uploaded {len(data)} bytes to s3://{self.bucket_name}/{clean_path}")
            return True
        except ClientError as e:
            logger.error(f"S3 upload_bytes failed for {clean_path}: {e}")
            return False

    def get_public_url(self, remote_path: str) -> str:
        clean_path = remote_path.lstrip("/")
        if self.cdn_base_url:
            return f"{self.cdn_base_url.rstrip('/')}/{clean_path}"
        if self.endpoint_url:
            return f"{self.endpoint_url.rstrip('/')}/{self.bucket_name}/{clean_path}"
        return f"https://{self.bucket_name}.s3.amazonaws.com/{clean_path}"

    def check_exists(self, remote_path: str) -> bool:
        clean_path = remote_path.lstrip("/")
        try:
            self.s3_client.head_object(Bucket=self.bucket_name, Key=clean_path)
            return True
        except ClientError:
            return False

    def read_bytes(self, remote_path: str) -> bytes | None:
        clean_path = remote_path.lstrip("/")
        try:
            res = self.s3_client.get_object(Bucket=self.bucket_name, Key=clean_path)
            return res["Body"].read()
        except ClientError as e:
            logger.error(f"Failed to read s3://{self.bucket_name}/{clean_path}: {e}")
            return None
