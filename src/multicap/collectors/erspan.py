from __future__ import annotations

from dataclasses import dataclass

from multicap.collectors.packets import CaptureCounters, CollectorResult, PacketRecord

ERSPAN_ETHERTYPE = 0x88BE


@dataclass(frozen=True, slots=True)
class ErspanFrame:
    timestamp: float
    ethertype: int
    payload: bytes
    session_id: int


class ErspanCollector:
    def collect(
        self,
        frames: list[ErspanFrame],
        *,
        device_id: str,
        interface: str,
    ) -> CollectorResult:
        packets: list[PacketRecord] = []
        dropped = 0
        for index, frame in enumerate(frames):
            if frame.ethertype != ERSPAN_ETHERTYPE:
                dropped += 1
                continue
            packets.append(
                PacketRecord(
                    packet_id=f"erspan-{device_id}-{index}",
                    timestamp=frame.timestamp,
                    payload=frame.payload,
                    device_id=device_id,
                    interface=interface,
                    mechanism="erspan",
                    metadata={"session_id": frame.session_id},
                )
            )
        return CollectorResult(tuple(packets), CaptureCounters(dropped=dropped))
