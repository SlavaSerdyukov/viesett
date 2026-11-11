import os
import re
import secrets
from pathlib import Path
from typing import Protocol


class PrivateObjectStorage(Protocol):
    def new_key(self) -> str: ...
    def put(self, key: str, content: bytes) -> None: ...
    def read(self, key: str) -> bytes: ...
    def delete(self, key: str) -> None: ...


class LocalPrivateStorage:
    """Dedicated private directory owned by the service, never mounted as static files."""

    def __init__(self, root: Path) -> None:
        if root.is_symlink():
            raise ValueError("Storage root cannot be a symlink")
        root.mkdir(mode=0o700, parents=True, exist_ok=True)
        self.root = root.resolve()
        self.root.chmod(0o700)

    def new_key(self) -> str:
        return secrets.token_hex(32)

    def _path(self, key: str) -> Path:
        if not re.fullmatch(r"[0-9a-f]{64}", key):
            raise ValueError("Invalid private object key")
        return self.root / key

    def put(self, key: str, content: bytes) -> None:
        descriptor = os.open(
            self._path(key), os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600
        )
        try:
            with os.fdopen(descriptor, "wb") as stream:
                stream.write(content)
                stream.flush()
                os.fsync(stream.fileno())
        except BaseException:
            self.delete(key)
            raise

    def read(self, key: str) -> bytes:
        descriptor = os.open(self._path(key), os.O_RDONLY | os.O_NOFOLLOW)
        with os.fdopen(descriptor, "rb") as stream:
            return stream.read()

    def delete(self, key: str) -> None:
        self._path(key).unlink(missing_ok=True)
