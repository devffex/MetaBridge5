import os
import shutil
import tempfile
from unittest.mock import MagicMock, patch

import pytest

from app.storage.factory import StorageFactory
from app.storage.github_backend import GitHubStorageBackend
from app.storage.local_backend import LocalStorageBackend
from app.storage.s3_backend import S3StorageBackend


@pytest.fixture
def temp_dir():
    d = tempfile.mkdtemp()
    yield d
    shutil.rmtree(d, ignore_errors=True)


def test_local_storage_backend(temp_dir):
    backend = LocalStorageBackend(base_dir=temp_dir, base_url="http://cdn.local")

    # Test upload_bytes
    data = b"hello world parquet test"
    path = "EURUSD/M1/data.parquet"
    assert backend.upload_bytes(data, path) is True
    assert backend.check_exists(path) is True
    assert backend.read_bytes(path) == data
    assert backend.get_public_url(path) == "http://cdn.local/EURUSD/M1/data.parquet"

    # Test upload_file
    local_file = os.path.join(temp_dir, "sample.json")
    with open(local_file, "w") as f:
        f.write('{"test": 123}')

    remote_file = "EURUSD/manifest.json"
    assert backend.upload_file(local_file, remote_file) is True
    assert backend.check_exists(remote_file) is True
    assert backend.read_bytes(remote_file) == b'{"test": 123}'


def test_storage_factory(temp_dir):
    StorageFactory.reset_cache()

    # Default fallback to local
    backend = StorageFactory.get_backend("local", base_dir=temp_dir)
    assert isinstance(backend, LocalStorageBackend)

    # Test GitHub instantiation
    backend_gh = StorageFactory.get_backend("github", token="fake", repo="user/repo")
    assert isinstance(backend_gh, GitHubStorageBackend)

    # Test S3 instantiation
    backend_s3 = StorageFactory.get_backend("s3", bucket_name="test-bucket")
    assert isinstance(backend_s3, S3StorageBackend)


@patch("httpx.Client")
def test_github_storage_backend(mock_client_class):
    mock_client = MagicMock()
    mock_client_class.return_value.__enter__.return_value = mock_client

    # Mock SHA lookup (404 = new file)
    mock_get_res = MagicMock()
    mock_get_res.status_code = 404
    mock_client.get.return_value = mock_get_res

    # Mock PUT commit response
    mock_put_res = MagicMock()
    mock_put_res.status_code = 201
    mock_client.put.return_value = mock_put_res

    backend = GitHubStorageBackend(token="test_token", repo="org/market-data", branch="main")
    assert backend.upload_bytes(b"data", "EURUSD/H1.parquet") is True
    assert (
        backend.get_public_url("EURUSD/H1.parquet")
        == "https://raw.githubusercontent.com/org/market-data/main/EURUSD/H1.parquet"
    )


@patch("boto3.client")
def test_s3_storage_backend(mock_boto_client):
    mock_s3 = MagicMock()
    mock_boto_client.return_value = mock_s3

    backend = S3StorageBackend(bucket_name="my-market-bucket", region_name="us-east-1")
    assert backend.upload_bytes(b"bytes", "EURUSD/H1.parquet") is True
    mock_s3.upload_fileobj.assert_called_once()
    assert backend.get_public_url("EURUSD/H1.parquet") == "https://my-market-bucket.s3.amazonaws.com/EURUSD/H1.parquet"
