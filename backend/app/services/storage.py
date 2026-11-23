"""Storage behind a service interface. Only LocalStorage exists today; an S3/Azure/GCS
backend implements the same methods and is selected in `get_storage`."""
import shutil
import uuid
from abc import ABC, abstractmethod
from pathlib import Path
from typing import BinaryIO

from ..config import get_settings

IMAGE_EXT = {".jpg", ".jpeg", ".png", ".webp"}
VIDEO_EXT = {".mp4", ".mov", ".avi", ".mkv", ".webm", ".m4v", ".mpeg", ".mpg"}


class StorageError(Exception):
    pass


class FileTooLarge(StorageError):
    pass


class StorageService(ABC):
    name = "abstract"

    @abstractmethod
    def save_reference(self, user_id: str, ext: str, stream: BinaryIO, max_bytes: int) -> str: ...

    @abstractmethod
    def save_video(self, user_id: str, ext: str, stream: BinaryIO, max_bytes: int) -> str: ...

    @abstractmethod
    def save_frame(self, search_id: str, frame_index: int, data: bytes) -> str: ...

    @abstractmethod
    def get_file(self, key: str) -> Path:
        """Return a local filesystem path for the key (cloud backends download to a cache)."""

    @abstractmethod
    def exists(self, key: str) -> bool: ...

    @abstractmethod
    def delete_file(self, key: str) -> None: ...

    @abstractmethod
    def delete_prefix(self, prefix: str) -> None: ...

    @abstractmethod
    def health(self) -> dict: ...


class LocalStorage(StorageService):
    name = "local"

    def __init__(self, root: Path):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def _safe(self, key: str) -> Path:
        path = (self.root / key).resolve()
        if self.root != path and self.root not in path.parents:
            raise StorageError("Invalid storage key")
        return path

    def _write(self, key: str, stream: BinaryIO, max_bytes: int) -> str:
        path = self._safe(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        written = 0
        try:
            with open(path, "wb") as out:
                while chunk := stream.read(1024 * 1024):
                    written += len(chunk)
                    if written > max_bytes:
                        raise FileTooLarge(f"File exceeds the {max_bytes // (1024 * 1024)} MB limit")
                    out.write(chunk)
        except Exception:
            path.unlink(missing_ok=True)
            raise
        return key

    def save_reference(self, user_id, ext, stream, max_bytes):
        return self._write(f"references/{user_id}/{uuid.uuid4().hex}{ext}", stream, max_bytes)

    def save_video(self, user_id, ext, stream, max_bytes):
        return self._write(f"videos/{user_id}/{uuid.uuid4().hex}{ext}", stream, max_bytes)

    def save_frame(self, search_id, frame_index, data):
        key = f"frames/{search_id}/{int(frame_index)}.jpg"
        path = self._safe(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return key

    def get_file(self, key):
        return self._safe(key)

    def exists(self, key):
        try:
            return self._safe(key).is_file()
        except StorageError:
            return False

    def delete_file(self, key):
        self._safe(key).unlink(missing_ok=True)

    def delete_prefix(self, prefix):
        path = self._safe(prefix)
        if path.is_dir():
            shutil.rmtree(path, ignore_errors=True)

    def health(self):
        probe = f"_health/{uuid.uuid4().hex}.tmp"
        path = self._safe(probe)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"ok")
        ok = path.read_bytes() == b"ok"
        path.unlink(missing_ok=True)
        usage = shutil.disk_usage(self.root)
        return {"ok": ok, "backend": self.name, "free_gb": round(usage.free / 1e9, 2)}


_storage: StorageService | None = None


def get_storage() -> StorageService:
    global _storage
    if _storage is None:
        _storage = LocalStorage(get_settings().data_dir / "media")
    return _storage


def reset_storage() -> None:
    global _storage
    _storage = None
