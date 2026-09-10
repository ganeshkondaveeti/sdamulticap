from __future__ import annotations

from multicap.collectors.peekremote import PeekremoteCollector, PeekremoteDatagram
from multicap.core.filters import FilterSpec
from multicap.core.topology import Device, TopologyGraph
from multicap.core.wireless import (
    AccessPoint,
    ApRestorationAssertion,
    ApStateSnapshot,
    ClientLocationResolver,
    SnifferApSelector,
    SnifferConsentRecord,
    WirelessController,
    WirelessInventory,
    WirelessPathSolver,
    WirelessSafetyGate,
    WlanProfile,
)
from multicap.core.wireless_correlator import RadioactiveTraceEvent, WirelessCorrelator


def main() -> int:
    topology = TopologyGraph()
    topology.add_device(Device("edge-1", "edge-1", "iosxe-switch", "ios-xe", "17.9", "192.0.2.10"))
    inventory = WirelessInventory(
        controllers={"wlc-1": WirelessController("wlc-1", "wlc-1", "192.0.2.50", "active", "17.9")},
        aps={
            "ap-1": AccessPoint("ap-1", "wlc-1", True, "edge-1", "Gi1/0/24", 0, "5GHz", 36, 80, 4)
        },
        wlans={"corp": WlanProfile("corp", "corp-policy", 20, "central")},
        client_bindings={"aa:bb:cc:dd:ee:ff": ("ap-1", "corp")},
    )
    location = ClientLocationResolver(inventory).resolve("aa:bb:cc:dd:ee:ff")
    plan = WirelessPathSolver(inventory, topology).solve_client_capture(
        job_id="phase8b-demo",
        client_mac=location.client_mac,
        filter_spec=FilterSpec(protocol="tcp", dst_port=443),
    )
    safety = WirelessSafetyGate().evaluate(
        location,
        SnifferApSelector().candidates(inventory, "wlc-1"),
        SnifferConsentRecord("phase8b-demo", "ap-1", "operator", True),
        live_channel=36,
    )
    packet = (
        PeekremoteCollector().collect([PeekremoteDatagram(2.0, b"PEEKHDR:auth", "ap-1")]).packets[0]
    )
    normalized = WirelessCorrelator().normalize_peekremote(packet, location)
    fused = WirelessCorrelator().fuse_radioactive_trace(
        [normalized], [RadioactiveTraceEvent(2.1, location.client_mac, "auth success")]
    )
    restored = ApRestorationAssertion().compare(
        ApStateSnapshot("ap-1", "local", "5GHz", 36, 80),
        ApStateSnapshot("ap-1", "local", "5GHz", 36, 80),
    )
    print(f"actions={[action.kind for action in plan.actions]}")
    print(f"safety={safety.allowed}")
    print(f"fused={len(fused)}")
    print(f"restored={restored.restored}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
