from __future__ import annotations

import pytest

from multicap.core.discovery import (
    CapabilityBackedProbe,
    StaticDeviceClassifier,
    SubnetSweeper,
    TopologyDiscoveryService,
    parse_cdp_neighbors_detail,
    parse_lldp_neighbors_detail,
)
from multicap.drivers.base import DeviceProfile
from multicap.drivers.capabilities import CapabilityRegistry

CDP_OUTPUT = """
Device ID: dist-1
Entry address(es):
  IP address: 192.0.2.2
Interface: GigabitEthernet1/0/1,  Port ID (outgoing port): Ethernet1/1
-----
Device ID: outside-1
Entry address(es):
  IP address: 198.51.100.2
Interface: GigabitEthernet1/0/2,  Port ID (outgoing port): Ethernet1/2
"""

LLDP_OUTPUT = """
System Name: access-2
Management Address: 192.0.2.3
Local Intf: GigabitEthernet1/0/3
Port id: Ethernet1/3
"""


class FixtureTransport:
    def __init__(self, outputs: dict[str, dict[str, str]]) -> None:
        self.outputs = outputs
        self.commands: list[tuple[str, str]] = []

    def execute(self, target: DeviceProfile, command: str, **kwargs: object) -> str:
        self.commands.append((target.id, command))
        return self.outputs.get(target.id, {}).get(command, "")


@pytest.fixture
def seed() -> DeviceProfile:
    return DeviceProfile("seed", "seed", "iosxe-switch", "ios-xe", "17.9")


@pytest.mark.unit
def test_cdp_and_lldp_parsers_extract_neighbors() -> None:
    cdp = parse_cdp_neighbors_detail(CDP_OUTPUT)
    lldp = parse_lldp_neighbors_detail(LLDP_OUTPUT)

    assert cdp[0].remote_host == "dist-1"
    assert cdp[0].local_interface == "GigabitEthernet1/0/1"
    assert lldp[0].remote_host == "access-2"
    assert lldp[0].remote_interface == "Ethernet1/3"


@pytest.mark.unit
def test_topology_crawl_enforces_hop_limit_and_cidr_allowlist(seed: DeviceProfile) -> None:
    dist = DeviceProfile("dist-1", "dist-1", "nxos", "nx-os", "10.2")
    access = DeviceProfile("access-2", "access-2", "iosxe-switch", "ios-xe", "17.12")
    transport = FixtureTransport(
        {
            "seed": {
                "show cdp neighbors detail": CDP_OUTPUT,
                "show lldp neighbors detail": LLDP_OUTPUT,
            },
            "dist-1": {
                "show cdp neighbors detail": "Device ID: deeper\nIP address: 192.0.2.4\nInterface: Eth1,  Port ID (outgoing port): Eth2",
                "show lldp neighbors detail": "",
            },
        }
    )
    classifier = StaticDeviceClassifier(
        {"seed": seed, "dist-1": dist, "192.0.2.2": dist, "access-2": access}
    )
    service = TopologyDiscoveryService(
        transport=transport,
        classifier=classifier,
        cidr_allowlist=["192.0.2.0/24"],
        hop_limit=0,
    )

    graph = service.crawl(seed, "192.0.2.1")

    assert sorted(graph.devices) == ["access-2", "dist-1", "seed"]
    assert len(graph.links) == 2
    assert all(device.management_ip.startswith("192.0.2.") for device in graph.devices.values())
    assert [command for device_id, command in transport.commands if device_id == "dist-1"] == []


@pytest.mark.unit
def test_subnet_sweep_uses_capability_backed_probe() -> None:
    registry = CapabilityRegistry.from_default_fixtures()
    probe = CapabilityBackedProbe(
        {
            "192.0.2.10": DeviceProfile("cat9k-10", "cat9k-10", "iosxe-switch", "ios-xe", "17.6"),
            "192.0.2.11": DeviceProfile("nexus-11", "nexus-11", "nxos", "nx-os", "9.3"),
        },
        registry,
    )
    graph = SubnetSweeper([probe], ["192.0.2.0/24"]).sweep("192.0.2.8/29")

    assert sorted(graph.devices) == ["cat9k-10", "nexus-11"]
    assert {device.source for device in graph.devices.values()} == {"subnet-ssh"}


@pytest.mark.unit
def test_subnet_sweep_rejects_outside_allowlist() -> None:
    sweeper = SubnetSweeper([], ["192.0.2.0/24"])

    with pytest.raises(ValueError, match="outside discovery allow-list"):
        sweeper.sweep("198.51.100.0/30")
