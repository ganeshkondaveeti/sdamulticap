from __future__ import annotations

from dataclasses import dataclass

from multicap.collectors.packets import PacketRecord
from multicap.core.wireless import ClientLocation


@dataclass(frozen=True, slots=True)
class RadioactiveTraceEvent:
    timestamp: float
    client_mac: str
    message: str


class WirelessCorrelator:
    def normalize_peekremote(self, packet: PacketRecord, location: ClientLocation) -> PacketRecord:
        payload = packet.payload[8:] if packet.payload.startswith(b"PEEKHDR:") else packet.payload
        return PacketRecord(
            packet.packet_id,
            packet.timestamp,
            payload,
            packet.device_id,
            "802.11",
            "ap-sniffer",
            {
                **packet.metadata,
                "band": location.band,
                "channel": location.channel,
                "width": location.channel_width_mhz,
            },
        )

    def capwap_inner_view(
        self, packet: PacketRecord, correlation_id: str
    ) -> tuple[PacketRecord, PacketRecord]:
        outer = PacketRecord(
            f"{packet.packet_id}-outer",
            packet.timestamp,
            packet.payload,
            packet.device_id,
            packet.interface,
            "capwap-outer",
            {**packet.metadata, "correlation_id": correlation_id},
        )
        inner_payload = packet.payload[4:] if len(packet.payload) > 4 else packet.payload
        inner = PacketRecord(
            f"{packet.packet_id}-inner",
            packet.timestamp,
            inner_payload,
            packet.device_id,
            packet.interface,
            "capwap-inner",
            {**packet.metadata, "correlation_id": correlation_id},
        )
        return outer, inner

    def fuse_radioactive_trace(
        self, packets: list[PacketRecord], events: list[RadioactiveTraceEvent]
    ) -> list[PacketRecord]:
        fused = list(packets)
        for index, event in enumerate(events):
            fused.append(
                PacketRecord(
                    f"radioactive-{index}",
                    event.timestamp,
                    event.message.encode(),
                    "wlc-radioactive-trace",
                    "control-plane",
                    "radioactive-trace",
                    {"client_mac": event.client_mac},
                )
            )
        return sorted(fused, key=lambda packet: (packet.timestamp, packet.packet_id))
