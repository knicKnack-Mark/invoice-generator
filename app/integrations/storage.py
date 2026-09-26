import os
import uuid
from abc import ABC, abstractmethod

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


def build_object_key(*, organization_id, original_filename: str) -> str:
    """Generates a random, non-guessable storage key. Never derived from the
    user-supplied filename directly (which we don't trust)."""
    ext = os.path.splitext(original_filename)[1][:10]  # cap a pathological extension
    return f"{organization_id}/{uuid.uuid4().hex}{ext}"


def get_storage_backend() -> StorageBackend:
    if settings.storage_backend == "local":
        return LocalStorageBackend(settings.storage_local_dir)
    raise NotImplementedError(
        f"Storage backend '{settings.storage_backend}' is not implemented yet. "
        "Add an S3Backend/R2Backend class here implementing StorageBackend and wire it in."
    )


storage_backend = get_storage_backend()
