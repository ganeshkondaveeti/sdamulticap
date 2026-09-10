from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

from multicap.collectors.packets import CaptureCounters, PacketRecord
from multicap.core.clock import ClockOffset


@dataclass(frozen=True, slots=True)
class CapwapOuterHeader:
    src_port: int
    dst_port: int
    is_capwap: bool


@dataclass(frozen=True, slots=True)
class CorrelatedPacket:
    packet_id: str
    timestamp: float
    device_id: str
    interface: str
    mechanism: str
    payload_hex: str
    offset_seconds: float
    metadata: dict[str, object]


@dataclass(frozen=True, slots=True)
class CorrelationSummary:
    output_path: Path
    packet_count: int
    dropped: int
    truncated: int


def parse_capwap_outer_header(raw_udp_header: bytes) -> CapwapOuterHeader:
    if len(raw_udp_header) < 4:
        raise ValueError("CAPWAP UDP header requires at least four bytes")
    src_port = int.from_bytes(raw_udp_header[0:2], "big")
    dst_port = int.from_bytes(raw_udp_header[2:4], "big")
    return CapwapOuterHeader(
        src_port, dst_port, src_port in {5246, 5247} or dst_port in {5246, 5247}
    )


class CorrelatorFacade:
    def merge(
        self,
        packets: list[PacketRecord],
        offsets: dict[str, ClockOffset],
        counters: dict[str, CaptureCounters],
        output_path: Path,
    ) -> CorrelationSummary:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        correlated = self._correlate(packets, offsets)
        output_path.write_text(
            "".join(json.dumps(asdict(packet), sort_keys=True) + "\n" for packet in correlated)
        )
        return CorrelationSummary(
            output_path=output_path,
            packet_count=len(correlated),
            dropped=sum(counter.dropped for counter in counters.values()),
            truncated=sum(counter.truncated for counter in counters.values()),
        )

    def _correlate(
        self, packets: list[PacketRecord], offsets: dict[str, ClockOffset]
    ) -> list[CorrelatedPacket]:
        seen: set[tuple[str, str]] = set()
        correlated: list[CorrelatedPacket] = []
        for packet in sorted(packets, key=lambda item: (item.timestamp, item.packet_id)):
            fingerprint = (packet.device_id, packet.payload.hex())
            if fingerprint in seen:
                continue
            seen.add(fingerprint)
            offset = offsets.get(packet.device_id, ClockOffset(packet.device_id, 0.0))
            correlated.append(
                CorrelatedPacket(
                    packet_id=packet.packet_id,
                    timestamp=offset.to_local(packet.timestamp),
                    device_id=packet.device_id,
                    interface=packet.interface,
                    mechanism=packet.mechanism,
                    payload_hex=packet.payload.hex(),
                    offset_seconds=offset.offset_seconds,
                    metadata=packet.metadata,
                )
            )
        return correlated
