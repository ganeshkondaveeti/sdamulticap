from __future__ import annotations

import ipaddress
import re
from collections import deque
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Protocol

from multicap.core.topology import Device, Link, TopologyGraph
from multicap.drivers.base import CommandTransport, DeviceProfile
from multicap.drivers.capabilities import CapabilityRegistry


@dataclass(frozen=True, slots=True)
class NeighborAdvertisement:
    remote_host: str
    local_interface: str
    remote_interface: str
    management_ip: str
    protocol: str


class DeviceClassifier(Protocol):
    def classify(self, host: str, management_ip: str) -> DeviceProfile | None: ...


class NetworkProbe(Protocol):
    method: str

    def probe(self, address: str) -> DeviceProfile | None: ...


class StaticDeviceClassifier:
    def __init__(self, devices: dict[str, DeviceProfile]) -> None:
        self._devices = devices

    def classify(self, host: str, management_ip: str) -> DeviceProfile | None:
        return self._devices.get(host) or self._devices.get(management_ip)


class CapabilityBackedProbe:
    method = "ssh"

    def __init__(self, devices: dict[str, DeviceProfile], registry: CapabilityRegistry) -> None:
        self._devices = devices
        self._registry = registry

    def probe(self, address: str) -> DeviceProfile | None:
        profile = self._devices.get(address)
        if profile is None:
            return None
        self._registry.probe(profile)
        return profile


class TopologyDiscoveryService:
    def __init__(
        self,
        transport: CommandTransport,
        classifier: DeviceClassifier,
        cidr_allowlist: Iterable[str],
        hop_limit: int,
    ) -> None:
        self._transport = transport
        self._classifier = classifier
        self._allowlist = [ipaddress.ip_network(cidr) for cidr in cidr_allowlist]
        self._hop_limit = hop_limit

    def crawl(self, seed: DeviceProfile, seed_management_ip: str) -> TopologyGraph:
        graph = TopologyGraph()
        queue: deque[tuple[DeviceProfile, str, int]] = deque([(seed, seed_management_ip, 0)])
        visited: set[str] = set()

        while queue:
            profile, management_ip, depth = queue.popleft()
            if profile.id in visited:
                continue
            visited.add(profile.id)
            graph.add_device(device_from_profile(profile, management_ip))

            cdp = self._transport.execute(profile, "show cdp neighbors detail")
            lldp = self._transport.execute(profile, "show lldp neighbors detail")
            for neighbor in [*parse_cdp_neighbors_detail(cdp), *parse_lldp_neighbors_detail(lldp)]:
                if not self._allowed(neighbor.management_ip):
                    continue
                remote_profile = self._classifier.classify(
                    neighbor.remote_host, neighbor.management_ip
                )
                if remote_profile is None:
                    continue
                graph.add_device(device_from_profile(remote_profile, neighbor.management_ip))
                graph.add_link(
                    Link(
                        local_device_id=profile.id,
                        local_interface=neighbor.local_interface,
                        remote_device_id=remote_profile.id,
                        remote_interface=neighbor.remote_interface,
                        protocol=neighbor.protocol,
                    )
                )
                if depth < self._hop_limit:
                    queue.append((remote_profile, neighbor.management_ip, depth + 1))
        return graph

    def _allowed(self, address: str) -> bool:
        ip = ipaddress.ip_address(address)
        return any(ip in network for network in self._allowlist)


class SubnetSweeper:
    def __init__(self, probes: Iterable[NetworkProbe], cidr_allowlist: Iterable[str]) -> None:
        self._probes = list(probes)
        self._allowlist = [ipaddress.ip_network(cidr) for cidr in cidr_allowlist]

    def sweep(self, cidr: str) -> TopologyGraph:
        network = ipaddress.ip_network(cidr)
        if not any(
            network.version == allowed.version
            and network.network_address in allowed
            and network.broadcast_address in allowed
            for allowed in self._allowlist
        ):
            raise ValueError(f"subnet {cidr} is outside discovery allow-list")
        graph = TopologyGraph()
        for address in network.hosts():
            host = str(address)
            for probe in self._probes:
                profile = probe.probe(host)
                if profile is not None:
                    graph.add_device(
                        device_from_profile(profile, host, source=f"subnet-{probe.method}")
                    )
                    break
        return graph


def device_from_profile(
    profile: DeviceProfile, management_ip: str, source: str = "discovery"
) -> Device:
    return Device(
        id=profile.id,
        host=profile.host,
        platform=profile.platform,
        os_family=profile.os_family,
        release_train=profile.release_train,
        management_ip=management_ip,
        source=source,
    )


def parse_cdp_neighbors_detail(output: str) -> list[NeighborAdvertisement]:
    blocks = re.split(r"^-{5,}\s*$", output, flags=re.MULTILINE)
    neighbors: list[NeighborAdvertisement] = []
    for block in blocks:
        host = _match(block, r"Device ID:\s*(\S+)")
        ip = _match(block, r"IP address:\s*([0-9.]+)")
        local = _match(block, r"Interface:\s*([^,]+),")
        remote = _match(block, r"Port ID \(outgoing port\):\s*(\S+)")
        if host and ip and local and remote:
            neighbors.append(
                NeighborAdvertisement(
                    remote_host=host,
                    local_interface=local.strip(),
                    remote_interface=remote.strip(),
                    management_ip=ip,
                    protocol="cdp",
                )
            )
    return neighbors


def parse_lldp_neighbors_detail(output: str) -> list[NeighborAdvertisement]:
    blocks = re.split(r"^-{5,}\s*$", output, flags=re.MULTILINE)
    neighbors: list[NeighborAdvertisement] = []
    for block in blocks:
        host = _match(block, r"System Name:\s*(\S+)")
        ip = _match(block, r"Management Address:\s*([0-9.]+)")
        local = _match(block, r"Local Intf:\s*(\S+)")
        remote = _match(block, r"Port id:\s*(\S+)")
        if host and ip and local and remote:
            neighbors.append(
                NeighborAdvertisement(
                    remote_host=host,
                    local_interface=local.strip(),
                    remote_interface=remote.strip(),
                    management_ip=ip,
                    protocol="lldp",
                )
            )
    return neighbors


def _match(content: str, pattern: str) -> str | None:
    match = re.search(pattern, content, flags=re.IGNORECASE)
    if match is None:
        return None
    return match.group(1).strip()
