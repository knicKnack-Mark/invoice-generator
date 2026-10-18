import asyncio
import os
import uuid
from abc import ABC, abstractmethod

import boto3
from botocore.exceptions import ClientError

from app.core.config import settings


class StorageBackend(ABC):
    @abstractmethod
    async def save(self, *, key: str, content: bytes) -> str:
        """Persist content under key, return a storage-relative reference."""

    @abstractmethod
    async def read(self, *, key: str) -> bytes:
        """Retrieve content by key. Raises FileNotFoundError if missing."""

    @abstractmethod
    async def delete(self, *, key: str) -> None:
        """Remove content by key. Silently no-ops if already missing."""


class LocalStorageBackend(StorageBackend):
    """Dev/small-deployment backend: stores files on local disk under
    STORAGE_LOCAL_DIR. Files are served back through an authenticated route
    (see app/api/v1/receipts.py) rather than a public static mount, so
    tenant checks still apply to every read."""

    def __init__(self, base_dir: str):
        self.base_dir = base_dir
        os.makedirs(self.base_dir, exist_ok=True)

    def _path(self, key: str) -> str:
        # key is always a generated UUID-based name (see build_object_key),
        # never derived from user input, so there's no path-traversal risk.
        return os.path.join(self.base_dir, key)

    async def save(self, *, key: str, content: bytes) -> str:
        path = self._path(key)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as f:
            f.write(content)
        return key

    async def read(self, *, key: str) -> bytes:
        with open(self._path(key), "rb") as f:
            return f.read()

    async def delete(self, *, key: str) -> None:
        try:
            os.remove(self._path(key))
        except FileNotFoundError:
            pass


class S3StorageBackend(StorageBackend):
    """Private S3-compatible object storage (AWS S3 or Cloudflare R2)."""

    def __init__(
        self,
        *,
        bucket: str,
        region: str,
        endpoint_url: str | None,
        access_key_id: str | None,
        secret_access_key: str | None,
    ):
        self.bucket = bucket
        self.client = boto3.client(
            "s3",
            region_name=region,
            endpoint_url=endpoint_url,
            aws_access_key_id=access_key_id,
            aws_secret_access_key=secret_access_key,
        )

    async def save(self, *, key: str, content: bytes) -> str:
        await asyncio.to_thread(self.client.put_object, Bucket=self.bucket, Key=key, Body=content)
        return key

    async def read(self, *, key: str) -> bytes:
        try:
            response = await asyncio.to_thread(self.client.get_object, Bucket=self.bucket, Key=key)
        except ClientError as exc:
            code = exc.response.get("Error", {}).get("Code")
            if code in {"404", "NoSuchKey", "NotFound"}:
                raise FileNotFoundError(key) from exc
            raise
        body = response["Body"]
        try:
            return await asyncio.to_thread(body.read)
        finally:
            await asyncio.to_thread(body.close)

    async def delete(self, *, key: str) -> None:
        await asyncio.to_thread(self.client.delete_object, Bucket=self.bucket, Key=key)


def build_object_key(*, organization_id, original_filename: str) -> str:
    """Generates a random, non-guessable storage key. Never derived from the
    user-supplied filename directly (which we don't trust)."""
    ext = os.path.splitext(original_filename)[1][:10]  # cap a pathological extension
    return f"{organization_id}/{uuid.uuid4().hex}{ext}"


def get_storage_backend() -> StorageBackend:
    if settings.storage_backend == "local":
        return LocalStorageBackend(settings.storage_local_dir)
    if settings.storage_backend in {"s3", "r2"}:
        if not settings.storage_bucket:
            raise RuntimeError("STORAGE_BUCKET is required when STORAGE_BACKEND is s3 or r2.")
        if bool(settings.storage_access_key_id) != bool(settings.storage_secret_access_key):
            raise RuntimeError(
                "STORAGE_ACCESS_KEY_ID and STORAGE_SECRET_ACCESS_KEY must be configured together."
            )
        if settings.storage_backend == "r2" and (
            not settings.storage_endpoint_url
            or not settings.storage_access_key_id
            or not settings.storage_secret_access_key
        ):
            raise RuntimeError(
                "STORAGE_ENDPOINT_URL, STORAGE_ACCESS_KEY_ID, and STORAGE_SECRET_ACCESS_KEY are required for R2."
            )
        return S3StorageBackend(
            bucket=settings.storage_bucket,
            region=settings.storage_region,
            endpoint_url=settings.storage_endpoint_url or None,
            access_key_id=settings.storage_access_key_id or None,
            secret_access_key=settings.storage_secret_access_key or None,
        )
    raise NotImplementedError(
        f"Storage backend '{settings.storage_backend}' is not supported. Choose 'local', 's3', or 'r2'."
    )


storage_backend = get_storage_backend()
