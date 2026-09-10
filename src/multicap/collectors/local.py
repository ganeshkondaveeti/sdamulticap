from __future__ import annotations

from collections.abc import Iterable

from multicap.collectors.packets import CollectorResult, PacketRecord


class LocalCaptureCollector:
    def collect(
        self, packets: Iterable[bytes], *, interface: str, started_at: float
    ) -> CollectorResult:
        return CollectorResult(
            tuple(
                PacketRecord(
                    packet_id=f"local-{interface}-{index}",
                    timestamp=started_at + index / 1000,
                    payload=payload,
                    device_id="local-capture-host",
                    interface=interface,
                    mechanism="local-nic",
                )
                for index, payload in enumerate(packets)
            )
        )
