from __future__ import annotations

import shutil
from contextlib import suppress
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path


@dataclass(frozen=True, slots=True)
class RetentionPolicy:
    max_age_days: int
    max_bytes: int


@dataclass(frozen=True, slots=True)
class StoredCapture:
    path: Path
    bytes_written: int


class PcapStore:
    def __init__(self, root: Path, retention: RetentionPolicy) -> None:
        self.root = root
        self.retention = retention
        self.root.mkdir(parents=True, exist_ok=True)

    def put(self, job_id: str, source: Path) -> StoredCapture:
        destination = self.root / job_id / source.name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        return StoredCapture(path=destination, bytes_written=destination.stat().st_size)

    def prune(self, now: datetime | None = None) -> list[Path]:
        current = now or datetime.now(UTC)
        deleted: list[Path] = []
        cutoff = current - timedelta(days=self.retention.max_age_days)
        files = sorted(self.root.glob("**/*.pcapng"), key=lambda path: path.stat().st_mtime)
        for path in list(files):
            modified = datetime.fromtimestamp(path.stat().st_mtime, UTC)
            if modified < cutoff:
                path.unlink()
                deleted.append(path)
                files.remove(path)

        total = sum(path.stat().st_size for path in files if path.exists())
        for path in files:
            if total <= self.retention.max_bytes:
                break
            size = path.stat().st_size
            path.unlink()
            deleted.append(path)
            total -= size
        self._remove_empty_dirs()
        return deleted

    def _remove_empty_dirs(self) -> None:
        for directory in sorted(
            (path for path in self.root.glob("**/*") if path.is_dir()), reverse=True
        ):
            with suppress(OSError):
                directory.rmdir()
