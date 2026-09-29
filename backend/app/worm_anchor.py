"""DEC05 G2 (docs/blueprint/BGP_DEC_Resolution_Intake_2026-09-25_ANSWERED.md,
Candidate A+): an asynchronous, independently-custodied, write-once copy of
each IntegrityCheckpoint's chain digest -- the external-custody half of
REQ-026/DEC05 that IntegrityCheckpoint's own docstring (app/models.py)
already names as the gap a same-Postgres-instance chain alone cannot close.

Same interface-then-swap-backend shape as app/attachment_storage.py.
`LocalWormAnchorStore` is a local-disk stand-in, not a real substitute for
S3 Object Lock (governance mode) or an equivalent externally-custodied
write-once store -- see the class docstring below for the honest limit.
"""

from __future__ import annotations

import os
from pathlib import Path

from app.core.config import settings


class WormAnchorStore:
    def write_once(self, key: str, payload: bytes) -> None:
        """Writes `payload` under `key`. MUST refuse (raise) if `key`
        already exists -- callers rely on this to detect a re-anchor
        attempt rather than silently overwriting prior anchored content."""
        raise NotImplementedError

    def read(self, key: str) -> bytes:
        raise NotImplementedError

    def exists(self, key: str) -> bool:
        raise NotImplementedError


class LocalWormAnchorStore(WormAnchorStore):
    """Refuses to overwrite an existing key -- the local stand-in for
    object-lock's write-once guarantee -- then chmods the file read-only as
    a second, best-effort local guard. Neither is a real substitute for S3
    Object Lock governance mode or equivalent: anyone with filesystem access
    to this process's host (or its own credential) can still chmod the file
    back to writable and overwrite it. Named honestly, same as
    attachment_storage.py's own local-disk caveat -- not fixed here."""

    def __init__(self, root: str | None = None):
        self.root = Path(root if root is not None else settings.worm_anchor_root)

    def _path(self, key: str) -> Path:
        return self.root / key

    def exists(self, key: str) -> bool:
        return self._path(key).exists()

    def write_once(self, key: str, payload: bytes) -> None:
        path = self._path(key)
        if path.exists():
            raise FileExistsError(f"WORM anchor already exists for key {key!r} -- refusing to overwrite")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(payload)
        os.chmod(path, 0o440)

    def read(self, key: str) -> bytes:
        return self._path(key).read_bytes()


worm_anchor_store: WormAnchorStore = LocalWormAnchorStore()
