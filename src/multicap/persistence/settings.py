from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from multicap.persistence.pcap_store import PcapStore, RetentionPolicy


@dataclass(frozen=True, slots=True)
class RetentionSettings:
    days: int = 30
    max_bytes: int = 10 * 1024 * 1024 * 1024

    def policy(self) -> RetentionPolicy:
        return RetentionPolicy(max_age_days=self.days, max_bytes=self.max_bytes)


class RetentionPruner:
    def __init__(self, root: Path, settings: RetentionSettings) -> None:
        self._store = PcapStore(root, settings.policy())

    def prune(self) -> list[Path]:
        return self._store.prune()
