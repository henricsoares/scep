from __future__ import annotations

import os
import re
import tempfile
from pathlib import Path
from typing import BinaryIO, Protocol
from uuid import UUID


class ArtifactStorageError(RuntimeError):
    pass


class DatasetArtifactStorage(Protocol):
    def store(self, export_id: UUID, content: bytes) -> str: ...
    def open(self, key: str) -> BinaryIO: ...
    def exists(self, key: str) -> bool: ...
    def delete(self, key: str) -> None: ...


SAFE_KEY = re.compile(r"^[0-9a-f-]{36}\.zip$")


class LocalDatasetArtifactStorage:
    def __init__(self, root: str | Path) -> None:
        self.root = Path(root).resolve()
        self.root.mkdir(mode=0o700, parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        if not SAFE_KEY.fullmatch(key):
            raise ArtifactStorageError("invalid artifact storage key")
        path = (self.root / key).resolve()
        if path.parent != self.root:
            raise ArtifactStorageError("invalid artifact storage key")
        return path

    def store(self, export_id: UUID, content: bytes) -> str:
        key = f"{export_id}.zip"
        target = self._path(key)
        temporary: str | None = None
        try:
            with tempfile.NamedTemporaryFile(
                dir=self.root, prefix=".partial-", delete=False
            ) as out:
                temporary = out.name
                os.chmod(temporary, 0o600)
                out.write(content)
                out.flush()
                os.fsync(out.fileno())
            os.replace(temporary, target)
            return key
        except OSError as exc:
            if temporary:
                Path(temporary).unlink(missing_ok=True)
            raise ArtifactStorageError("artifact storage operation failed") from exc

    def open(self, key: str) -> BinaryIO:
        try:
            return self._path(key).open("rb")
        except OSError as exc:
            raise ArtifactStorageError("artifact storage operation failed") from exc

    def exists(self, key: str) -> bool:
        try:
            return self._path(key).is_file()
        except OSError as exc:
            raise ArtifactStorageError("artifact storage operation failed") from exc

    def delete(self, key: str) -> None:
        try:
            self._path(key).unlink(missing_ok=True)
        except OSError as exc:
            raise ArtifactStorageError("artifact storage operation failed") from exc
