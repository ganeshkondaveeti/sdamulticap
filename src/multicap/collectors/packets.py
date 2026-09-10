from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class PacketRecord:
    packet_id: str
    timestamp: float
    payload: bytes
    device_id: str
    interface: str
    mechanism: str
    metadata: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class CaptureCounters:
    dropped: int = 0
    truncated: int = 0


@dataclass(frozen=True, slots=True)
class CollectorResult:
    packets: tuple[PacketRecord, ...]
    counters: CaptureCounters = CaptureCounters()
