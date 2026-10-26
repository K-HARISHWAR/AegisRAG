"""Storage provider abstraction and local filesystem implementation."""

import os
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()


class StorageProvider(ABC):
    """Abstract interface for document file storage."""

    @abstractmethod
    async def save_file(self, storage_key: str, file_bytes: bytes) -> str:
        """Save raw document bytes to storage and return storage key."""
        pass

    @abstractmethod
    async def read_file(self, storage_key: str) -> bytes:
        """Read and return document bytes from storage."""
        pass

    @abstractmethod
    async def delete_file(self, storage_key: str) -> bool:
        """Idempotently delete document file from storage."""
        pass

    @abstractmethod
    async def exists(self, storage_key: str) -> bool:
        """Check if file exists in storage."""
        pass


class LocalStorageProvider(StorageProvider):
    """Local filesystem storage provider with directory traversal defense."""

    def __init__(self, base_directory: str | None = None) -> None:
        self.base_dir = Path(base_directory or settings.LOCAL_STORAGE_DIR).resolve()
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def _resolve_safe_path(self, storage_key: str) -> Path:
        """Resolve absolute path and ensure it does not escape base directory."""
        # Sanitize storage key to prevent directory traversal
        sanitized_key = Path(storage_key).name
        target_path = (self.base_dir / sanitized_key).resolve()

        if not str(target_path).startswith(str(self.base_dir)):
            raise ValueError(f"Path traversal attempt detected in storage key '{storage_key}'")

        return target_path

    async def save_file(self, storage_key: str, file_bytes: bytes) -> str:
        """Save file bytes safely to local storage directory."""
        safe_path = self._resolve_safe_path(storage_key)
        safe_path.parent.mkdir(parents=True, exist_ok=True)

        with open(safe_path, "wb") as f:
            f.write(file_bytes)

        logger.info("Saved file to local storage: %s (%d bytes)", storage_key, len(file_bytes))
        return storage_key

    async def read_file(self, storage_key: str) -> bytes:
        """Read raw bytes for stored document."""
        safe_path = self._resolve_safe_path(storage_key)
        if not safe_path.is_file():
            raise FileNotFoundError(f"Stored document '{storage_key}' not found on disk")

        with open(safe_path, "rb") as f:
            return f.read()

    async def delete_file(self, storage_key: str) -> bool:
        """Idempotently delete file from local storage."""
        try:
            safe_path = self._resolve_safe_path(storage_key)
            if safe_path.is_file():
                safe_path.unlink()
                logger.info("Deleted file from storage: %s", storage_key)
                return True
            return False
        except Exception as exc:
            logger.warning("Error during file deletion for %s: %s", storage_key, str(exc))
            return False

    async def exists(self, storage_key: str) -> bool:
        """Check if storage key exists on disk."""
        try:
            safe_path = self._resolve_safe_path(storage_key)
            return safe_path.is_file()
        except Exception:
            return False


def get_storage_provider() -> StorageProvider:
    """Dependency / factory returning the configured storage provider."""
    return LocalStorageProvider()
