from __future__ import annotations

from multicap.core.discovery import StaticDeviceClassifier, TopologyDiscoveryService
from multicap.drivers.base import DeviceProfile


class DemoTransport:
    def execute(self, target: DeviceProfile, command: str, **kwargs: object) -> str:
        if target.id != "seed":
            return ""
        if command == "show cdp neighbors detail":
            return """
Device ID: dist-1
Entry address(es):
  IP address: 192.0.2.2
Interface: GigabitEthernet1/0/1,  Port ID (outgoing port): Ethernet1/1
"""
        if command == "show lldp neighbors detail":
            return """
System Name: access-2
Management Address: 192.0.2.3
Local Intf: GigabitEthernet1/0/3
Port id: Ethernet1/3
"""
        return ""


def main() -> int:
    seed = DeviceProfile("seed", "seed", "iosxe-switch", "ios-xe", "17.9")
    dist = DeviceProfile("dist-1", "dist-1", "nxos", "nx-os", "10.2")
    access = DeviceProfile("access-2", "access-2", "iosxe-switch", "ios-xe", "17.12")
    graph = TopologyDiscoveryService(
        transport=DemoTransport(),
        classifier=StaticDeviceClassifier({"seed": seed, "dist-1": dist, "access-2": access}),
        cidr_allowlist=["192.0.2.0/24"],
        hop_limit=1,
    ).crawl(seed, "192.0.2.1")
    print(f"devices={sorted(graph.devices)}")
    print(f"links={len(graph.links)}")
    print(f"seed_neighbors={[device.id for device in graph.neighbors('seed')]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
