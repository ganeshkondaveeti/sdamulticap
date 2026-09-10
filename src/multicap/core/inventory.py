from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from multicap.core.topology import Device, Link, TopologyGraph
from multicap.transport.restconf import RestconfClient


@dataclass(frozen=True, slots=True)
class InventorySnapshot:
    devices: tuple[Device, ...] = ()
    links: tuple[Link, ...] = ()


class InventorySource(Protocol):
    name: str
    enabled: bool

    def load(self) -> InventorySnapshot: ...


@dataclass(slots=True)
class CatalystCenterInventorySource:
    client: RestconfClient
    enabled: bool = True
    name: str = "catalyst-center"

    def load(self) -> InventorySnapshot:
        payload = self.client.get_json("dna/intent/api/v1/network-device")
        if not isinstance(payload, dict):
            raise ValueError("Catalyst Center inventory response must be an object")
        raw_devices = payload.get("response", [])
        if not isinstance(raw_devices, list):
            raise ValueError("Catalyst Center inventory response must contain a list")
        devices: list[Device] = []
        for raw in raw_devices:
            if isinstance(raw, dict):
                devices.append(
                    Device(
                        id=str(raw["id"]),
                        host=str(raw.get("hostname", raw["id"])),
                        platform=str(raw.get("platformId", "unknown")),
                        os_family=str(raw.get("softwareType", "unknown")),
                        release_train=str(raw.get("softwareVersion", "unknown")),
                        management_ip=str(raw["managementIpAddress"]),
                        source=self.name,
                    )
                )
        return InventorySnapshot(devices=tuple(devices))


@dataclass(slots=True)
class StaticInventorySource:
    name: str
    snapshot: InventorySnapshot = field(default_factory=InventorySnapshot)
    enabled: bool = False

    def load(self) -> InventorySnapshot:
        return self.snapshot


class InventoryIngestService:
    def __init__(self, sources: list[InventorySource]) -> None:
        self._sources = sources

    def ingest(self, graph: TopologyGraph | None = None) -> TopologyGraph:
        target = graph or TopologyGraph()
        for source in self._sources:
            if not source.enabled:
                continue
            snapshot = source.load()
            for device in snapshot.devices:
                target.add_device(device)
            for link in snapshot.links:
                target.add_link(link)
        return target


def thin_inventory_sources() -> list[StaticInventorySource]:
    return [
        StaticInventorySource("prime"),
        StaticInventorySource("nso"),
        StaticInventorySource("nexus-dashboard"),
        StaticInventorySource("apic"),
    ]
