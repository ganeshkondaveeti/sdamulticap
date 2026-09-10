from __future__ import annotations

from dataclasses import dataclass, field

from multicap.drivers.base import DeviceProfile


@dataclass(frozen=True, slots=True)
class Device:
    id: str
    host: str
    platform: str
    os_family: str
    release_train: str
    management_ip: str
    sys_object_id: str | None = None
    source: str = "discovery"

    def profile(self) -> DeviceProfile:
        return DeviceProfile(
            id=self.id,
            host=self.host,
            platform=self.platform,
            os_family=self.os_family,
            release_train=self.release_train,
        )


@dataclass(frozen=True, slots=True)
class Link:
    local_device_id: str
    local_interface: str
    remote_device_id: str
    remote_interface: str
    protocol: str

    def key(self) -> tuple[str, str, str, str, str]:
        left = (self.local_device_id, self.local_interface)
        right = (self.remote_device_id, self.remote_interface)
        if right < left:
            left, right = right, left
        return (left[0], left[1], right[0], right[1], self.protocol.lower())


@dataclass(slots=True)
class TopologyGraph:
    devices: dict[str, Device] = field(default_factory=dict)
    links: dict[tuple[str, str, str, str, str], Link] = field(default_factory=dict)

    def add_device(self, device: Device) -> None:
        self.devices[device.id] = device

    def add_link(self, link: Link) -> None:
        self.links[link.key()] = link

    def neighbors(self, device_id: str) -> list[Device]:
        neighbor_ids: set[str] = set()
        for link in self.links.values():
            if link.local_device_id == device_id:
                neighbor_ids.add(link.remote_device_id)
            if link.remote_device_id == device_id:
                neighbor_ids.add(link.local_device_id)
        return [self.devices[neighbor_id] for neighbor_id in sorted(neighbor_ids)]

    def profiles(self) -> list[DeviceProfile]:
        return [
            device.profile() for device in sorted(self.devices.values(), key=lambda item: item.id)
        ]
