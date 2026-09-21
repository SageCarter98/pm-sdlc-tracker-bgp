"""WP15 Phase 1: local-disk storage for uploaded evidence attachments
(FE-097/098). `AttachmentStore` is the seam a later S3-compatible
implementation would replace -- nothing outside this module should know
files currently live on local disk.

storage_key is always server-generated here (tenant_id + a fresh uuid4),
never derived from the client's filename -- nothing reads a client-supplied
path component when resolving a file on disk, so there is no path-traversal
surface regardless of what a caller names an upload."""

from __future__ import annotations

import hashlib
import uuid
from pathlib import Path

from app.core.config import settings


class AttachmentStore:
    def save(self, tenant_id: str, data: bytes) -> tuple[str, str]:
        """Persist `data`, return (storage_key, checksum_sha256)."""
        raise NotImplementedError

    def read(self, storage_key: str) -> bytes:
        raise NotImplementedError


class LocalDiskAttachmentStore(AttachmentStore):
    def __init__(self, root: str | None = None):
        self.root = Path(root if root is not None else settings.attachment_storage_root)

    def _path(self, storage_key: str) -> Path:
        return self.root / storage_key

    def save(self, tenant_id: str, data: bytes) -> tuple[str, str]:
        checksum = hashlib.sha256(data).hexdigest()
        storage_key = f"{tenant_id}/{uuid.uuid4()}"
        path = self._path(storage_key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return storage_key, checksum

    def read(self, storage_key: str) -> bytes:
        return self._path(storage_key).read_bytes()


attachment_store: AttachmentStore = LocalDiskAttachmentStore()
