from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from multicap.persistence.pcap_store import PcapStore, RetentionPolicy


@dataclass(frozen=True, slots=True)
class RetentionSettings:
    days: int = 30
    max_bytes: int = 10 * 1024 * 1024 * 1024

    def policy(self) -> RetentionPolicy:
        return RetentionPolicy(max_age_days=self.days, max_bytes=self.max_bytes)


@dataclass(frozen=True, slots=True)
class RetentionUsage:
    settings: RetentionSettings
    current_bytes: int
    last_pruned: str
    pruned_paths: tuple[Path, ...]


class RetentionPruner:
    def __init__(self, root: Path, settings: RetentionSettings) -> None:
        self._root: Path = root
        self._settings: RetentionSettings = settings
        self._store: PcapStore = PcapStore(root, settings.policy())

    def prune(self) -> list[Path]:
        return self._store.prune()

    def usage(self, pruned_paths: list[Path] | None = None) -> RetentionUsage:
        files = [path for path in self._root.glob("**/*.pcapng") if path.is_file()]
        return RetentionUsage(
            self._settings,
            sum(path.stat().st_size for path in files),
            datetime.now(UTC).isoformat(),
            tuple(pruned_paths or []),
        )
