from __future__ import annotations

from dataclasses import dataclass

from multicap.collectors.packets import CollectorResult, PacketRecord


@dataclass(frozen=True, slots=True)
class PeekremoteDatagram:
    timestamp: float
    payload: bytes
    ap_name: str


class PeekremoteCollector:
    def collect(self, datagrams: list[PeekremoteDatagram]) -> CollectorResult:
        return CollectorResult(
            tuple(
                PacketRecord(
                    packet_id=f"peekremote-{datagram.ap_name}-{index}",
                    timestamp=datagram.timestamp,
                    payload=datagram.payload,
                    device_id=datagram.ap_name,
                    interface="radio",
                    mechanism="peekremote",
                    metadata={"stub": True},
                )
                for index, datagram in enumerate(datagrams)
            )
        )
